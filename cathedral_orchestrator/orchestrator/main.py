import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import FastAPI, Request, HTTPException
from starlette.responses import JSONResponse, StreamingResponse, PlainTextResponse  # noqa: F401

from .logging_config import setup_logging, jlog
from .sse import sse_proxy
from .vector.chroma_client import ChromaClient, ChromaConfig
from .toolbridge import ToolBridge
from .mpc_server import router as mpc_router, MPCServer, set_server, get_server

logger = setup_logging(os.environ.get("LOG_LEVEL","INFO"))

APP_CLIENTS: Dict[str, httpx.AsyncClient] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    APP_CLIENTS["lm"] = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30, write=30, read=None, pool=None),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    APP_CLIENTS["chroma"] = httpx.AsyncClient(
        timeout=30,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    try:
        yield
    finally:
        await asyncio.gather(*(client.aclose() for client in APP_CLIENTS.values()))
        APP_CLIENTS.clear()


app = FastAPI(title="Cathedral Orchestrator", lifespan=lifespan)

# Load options from /data/options.json inside HA add-on container
OPTIONS_PATH = os.environ.get("CATHEDRAL_OPTIONS_PATH","/data/options.json")

def load_options() -> Dict[str,Any]:
    with open(OPTIONS_PATH,"r",encoding="utf-8") as f:
        return json.load(f)

opts = load_options()


def _normalize_lm_hosts(raw) -> Dict[str, str]:
    # Accept dict, list[str], or str; return {name: url}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {f"h{i}": str(u) for i, u in enumerate(raw)}
    if isinstance(raw, str):
        return {"primary": raw}
    return {}


LM_HOSTS: Dict[str, str] = _normalize_lm_hosts(opts.get("lm_hosts", {}))
CHROMA_MODE: str = opts.get("chroma_mode", "http")  # "http" | "embedded"
CHROMA_URL: str = opts.get("chroma_url", "http://127.0.0.1:8000")
PERSIST_DIR: str = opts.get("chroma_persist_dir", "/data/chroma")
COLLECTION_NAME: str = opts.get("collection_name","cathedral")
ALLOWED_DOMAINS: List[str] = opts.get("allowed_domains", ["light","switch","scene"])
TEMP: float = float(opts.get("temperature",0.7))
TOP_P: float = float(opts.get("top_p",0.9))
UPSERTS_ENABLED: bool = bool(opts.get("upserts_enabled", True))

# Initialize clients
chroma = ChromaClient(
    ChromaConfig(
        mode=CHROMA_MODE,
        url=CHROMA_URL,
        collection_name=COLLECTION_NAME,
        persist_dir=PERSIST_DIR,
    )
)
tb = ToolBridge(ALLOWED_DOMAINS)
set_server(MPCServer(toolbridge=tb, chroma=chroma))

app.include_router(mpc_router)

async def list_models_from_host(client: httpx.AsyncClient, base: str) -> Tuple[str, List[Dict[str,Any]]]:
    url = base.rstrip("/") + "/v1/models"
    try:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        models = data.get("data", [])
        return (base, models)
    except Exception as e:
        jlog(logger, level="WARN", event="lm_models_fail", host=base, error=str(e))
        return (base, [])

def build_model_index(host_models: List[Tuple[str,List[Dict[str,Any]]]]) -> Dict[str,str]:
    idx = {}
    for base, models in host_models:
        for m in models:
            mid = m.get("id") or m.get("name")
            if not mid:
                continue
            # first one wins; deterministic routing per spec
            if mid not in idx:
                idx[mid] = base
    return idx

@app.get("/health")
async def health():
    # Composite health
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    tasks = [list_models_from_host(client, base) for base in LM_HOSTS.values()]
    results = await asyncio.gather(*tasks)
    chroma_ok = chroma.health()
    return JSONResponse({"ok": True, "lm_hosts": {base: len(models) for base,models in results}, "chroma": {"ok": chroma_ok}})

@app.get("/api/status")
async def api_status():
    return JSONResponse({"ts": time.time(), "options": opts})

@app.get("/api/options")
async def api_options():
    return JSONResponse(opts)

@app.post("/api/options")
async def api_set_options(request: Request):
    # Hot-apply at runtime; also advise UI to persist to add-on options via Supervisor API for restart-persistence
    new_opts = await request.json()
    opts.update(new_opts)
    global LM_HOSTS, CHROMA_MODE, CHROMA_URL, PERSIST_DIR, COLLECTION_NAME, ALLOWED_DOMAINS, TEMP, TOP_P, UPSERTS_ENABLED, chroma
    LM_HOSTS = _normalize_lm_hosts(opts.get("lm_hosts", LM_HOSTS))
    CHROMA_MODE = opts.get("chroma_mode", CHROMA_MODE)
    CHROMA_URL = opts.get("chroma_url", CHROMA_URL)
    PERSIST_DIR = opts.get("chroma_persist_dir", PERSIST_DIR)
    COLLECTION_NAME = opts.get("collection_name", COLLECTION_NAME)
    ALLOWED_DOMAINS = opts.get("allowed_domains", ALLOWED_DOMAINS)
    TEMP = float(opts.get("temperature", TEMP))
    TOP_P = float(opts.get("top_p", TOP_P))
    UPSERTS_ENABLED = bool(opts.get("upserts_enabled", UPSERTS_ENABLED))
    tb.allowed_domains = set(ALLOWED_DOMAINS)
    chroma = ChromaClient(
        ChromaConfig(
            mode=CHROMA_MODE,
            url=CHROMA_URL,
            collection_name=COLLECTION_NAME,
            persist_dir=PERSIST_DIR,
        )
    )
    try:
        server = get_server()
        server.chroma = chroma
    except RuntimeError:
        # Server will be initialized below on first boot.
        pass
    return JSONResponse({"ok": True, "applied": new_opts})

@app.get("/v1/models")
async def list_models():
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    tasks = [list_models_from_host(client, base) for base in LM_HOSTS.values()]
    results = await asyncio.gather(*tasks)
    # Merge into OpenAI shape
    union = []
    for base, models in results:
        for m in models:
            if "id" in m:
                union.append(m)
            elif "name" in m:
                m2 = {"id": m["name"], **{k:v for k,v in m.items() if k!="name"}}
                union.append(m2)
    return JSONResponse({"object":"list","data": union})

async def _route_for_model(model: str) -> str:
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    tasks = [list_models_from_host(client, base) for base in LM_HOSTS.values()]
    results = await asyncio.gather(*tasks)
    idx = build_model_index(results)
    return idx.get(model) or list(LM_HOSTS.values())[0]

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model")
    target = await _route_for_model(model) if model else list(LM_HOSTS.values())[0]
    url = target.rstrip("/") + "/v1/chat/completions"
    stream = bool(body.get("stream", True))
    headers = {"Content-Type":"application/json"}
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    if stream:
        t = httpx.Timeout(connect=30, write=30, read=None, pool=None)
        async with client.stream("POST", url, headers=headers, json=body, timeout=t) as upstream:
            async def gen():
                async for chunk in upstream.aiter_raw():
                    yield chunk
            return await sse_proxy(gen())
    else:
        r = await client.post(url, headers=headers, json=body)
        return JSONResponse(r.json(), status_code=r.status_code)

@app.post("/v1/embeddings")
async def embeddings(request: Request):
    body = await request.json()
    model = body.get("model")
    target = await _route_for_model(model) if model else list(LM_HOSTS.values())[0]
    url = target.rstrip("/") + "/v1/embeddings"
    headers = {"Content-Type":"application/json"}

    # Determine inputs (text or list) to match OpenAI shape
    raw_input = body.get("input")
    if isinstance(raw_input, str):
        inputs_list = [raw_input]
    elif isinstance(raw_input, list):
        inputs_list = [x if isinstance(x, str) else (str(x) if x is not None else "") for x in raw_input]
    else:
        inputs_list = []

    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    r = await client.post(url, headers=headers, json=body)
    r.raise_for_status()
    data = r.json()
    # Upsert to Chroma with metadata (guarded)
    try:
        if UPSERTS_ENABLED:
            payload_items = data.get("data") or []
            vectors = [item.get("embedding") for item in payload_items]
            texts = inputs_list[:len(vectors)]
            if len(texts) < len(vectors):
                texts.extend(["" for _ in range(len(vectors) - len(texts))])
            ids = [str(uuid.uuid4()) for _ in vectors]
            meta = body.get("metadata") or {}
            metadatas = [meta for _ in vectors]
            chroma_res = chroma.upsert(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
            jlog(logger, event="chroma_upsert", result=chroma_res, count=len(vectors))
    except Exception as e:
        jlog(logger, level="ERROR", event="chroma_upsert_fail", error=str(e))
    return JSONResponse(data, status_code=r.status_code)
