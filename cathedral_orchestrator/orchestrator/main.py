import asyncio
import json
import os
import uuid
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse
from starlette.responses import PlainTextResponse  # noqa: F401
from starlette.responses import StreamingResponse  # noqa: F401

from . import sessions
from .logging_config import jlog, setup_logging
from .mpc_server import MPCServer, get_server, router as mpc_router, set_server
from .sse import sse_proxy
from .toolbridge import ToolBridge
from .vector.chroma_client import ChromaClient, ChromaConfig

logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

APP_CLIENTS: Dict[str, httpx.AsyncClient] = {}
OPTIONS_PATH = Path(os.environ.get("CATHEDRAL_OPTIONS_PATH", "/data/options.json"))
OPTIONS_LOCK = asyncio.Lock()


def load_options_from_disk() -> Dict[str, Any]:
    try:
        with OPTIONS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
            jlog(logger, level="ERROR", event="options_invalid_shape")
    except FileNotFoundError:
        jlog(logger, level="WARN", event="options_missing", path=str(OPTIONS_PATH))
    except json.JSONDecodeError as exc:
        jlog(logger, level="ERROR", event="options_json_error", error=str(exc))
    except Exception as exc:  # pragma: no cover - defensive guard
        jlog(logger, level="ERROR", event="options_load_failed", error=str(exc))
    return {}


def persist_options_to_disk(options: Dict[str, Any]) -> None:
    payload = json.dumps(options, indent=2, sort_keys=True)
    temp_path = OPTIONS_PATH.with_suffix(".tmp")
    try:
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(OPTIONS_PATH)
        jlog(logger, event="options_persisted", path=str(OPTIONS_PATH))
    except Exception as exc:  # pragma: no cover - filesystem guard
        jlog(logger, level="ERROR", event="options_write_failed", error=str(exc))
        print(f"[orchestrator] Failed to persist options: {exc}")
        raise


def _normalize_lm_hosts(raw: Any) -> Dict[str, str]:
    def _clean(url: str) -> str:
        value = (url or "").strip().rstrip("/")
        return value[:-3] if value.endswith("/v1") else value

    if isinstance(raw, dict):
        return {name: _clean(url) for name, url in raw.items() if url}
    if isinstance(raw, list):
        return {
            f"host_{index + 1}": _clean(url) for index, url in enumerate(raw) if url
        }
    if isinstance(raw, str) and raw:
        return {"primary": _clean(raw)}
    return {}


async def list_models_from_host(
    client: httpx.AsyncClient, base: str
) -> Tuple[str, List[Dict[str, Any]]]:
    url = base.rstrip("/") + "/v1/models"
    try:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = data.get("data", [])
        return base, models if isinstance(models, list) else []
    except Exception as exc:  # pragma: no cover - network guard
        jlog(logger, level="WARN", event="lm_models_fail", host=base, error=str(exc))
        return base, []


def build_model_index(
    host_models: List[Tuple[str, List[Dict[str, Any]]]],
) -> Dict[str, str]:
    index: Dict[str, str] = {}
    for base, models in host_models:
        for model in models:
            model_id = model.get("id") or model.get("name")
            if not model_id:
                continue
            if model_id not in index:
                index[model_id] = base
    return index


class HostPool:
    def __init__(self, hosts: Dict[str, str]):
        self._hosts = hosts
        self._catalog: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    def update_hosts(self, hosts: Dict[str, str]) -> None:
        self._hosts = hosts

    def list_hosts(self) -> List[str]:
        return list(self._hosts.values())

    def has_hosts(self) -> bool:
        return bool(self._hosts)

    async def refresh(
        self, client: httpx.AsyncClient
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self._hosts:
            async with self._lock:
                self._catalog = {}
            jlog(logger, level="DEBUG", event="hostpool_refresh", hosts=0)
            return {}

        tasks = [list_models_from_host(client, base) for base in self._hosts.values()]
        results = await asyncio.gather(*tasks)
        catalog = {base: models for base, models in results}
        async with self._lock:
            self._catalog = catalog
        counts = {base: len(models) for base, models in catalog.items()}
        jlog(logger, event="hostpool_refreshed", counts=counts)
        return catalog

    async def get_catalog(self) -> Dict[str, List[str]]:
        async with self._lock:
            response: Dict[str, List[str]] = {}
            for base, models in self._catalog.items():
                ids: List[str] = []
                for model in models:
                    if isinstance(model, dict):
                        model_id = model.get("id") or model.get("name")
                    else:
                        model_id = str(model)
                    if model_id:
                        ids.append(str(model_id))
                response[base] = ids
            return response

    def is_ready(self) -> bool:
        return self.has_hosts()


class SessionManager:
    async def list_active(self) -> int:
        count = await sessions.list_active()
        return int(count)


CURRENT_OPTIONS = load_options_from_disk()
LM_HOSTS: Dict[str, str] = _normalize_lm_hosts(CURRENT_OPTIONS.get("lm_hosts"))
CHROMA_MODE: str = "http"
CHROMA_URL: str = CURRENT_OPTIONS.get("chroma_url", "http://127.0.0.1:8000")
COLLECTION_NAME: str = CURRENT_OPTIONS.get("collection_name", "cathedral")
ALLOWED_DOMAINS: List[str] = CURRENT_OPTIONS.get(
    "allowed_domains", ["light", "switch", "scene"]
)
TEMP: float = float(CURRENT_OPTIONS.get("temperature", 0.7))
TOP_P: float = float(CURRENT_OPTIONS.get("top_p", 0.9))
AUTO_CONFIG_REQUESTED: bool = bool(CURRENT_OPTIONS.get("auto_config", True))
UPSERTS_REQUESTED: bool = bool(CURRENT_OPTIONS.get("upserts_enabled", True))
AUTO_CONFIG_ACTIVE: bool = False
UPSERTS_ACTIVE: bool = False

HOST_POOL: Optional[HostPool] = HostPool(LM_HOSTS)
SESSION_MANAGER = SessionManager()
BOOTSTRAP_EVENT = asyncio.Event()

PRUNE_INTERVAL_SECONDS = 15 * 60
SESSION_TTL_MINUTES = 120

_prune_thread: Optional[threading.Thread] = None
_prune_stop = threading.Event()


def _prune_loop() -> None:
    global _prune_thread
    jlog(
        logger,
        event="session_prune_loop_started",
        ttl_minutes=SESSION_TTL_MINUTES,
        interval_seconds=PRUNE_INTERVAL_SECONDS,
    )
    while not _prune_stop.is_set():
        try:
            pruned = asyncio.run(sessions.prune_idle(ttl_minutes=SESSION_TTL_MINUTES))
            jlog(
                logger,
                event="session_prune_cycle",
                pruned=pruned,
                ttl_minutes=SESSION_TTL_MINUTES,
            )
        except Exception as exc:  # pragma: no cover - scheduler guard
            jlog(
                logger,
                level="ERROR",
                event="session_prune_cycle_failed",
                error=str(exc),
                ttl_minutes=SESSION_TTL_MINUTES,
            )
        if _prune_stop.wait(PRUNE_INTERVAL_SECONDS):
            break
    jlog(logger, event="session_prune_loop_stopped")
    _prune_thread = None


def _start_pruner_if_needed() -> None:
    global _prune_thread
    if _prune_thread and _prune_thread.is_alive():
        jlog(logger, event="session_prune_loop_active")
        return
    _prune_stop.clear()
    _prune_thread = threading.Thread(
        target=_prune_loop,
        name="ttl-pruner",
        daemon=True,
    )
    _prune_thread.start()
    jlog(logger, event="session_prune_loop_spawned")


def stop_pruner() -> None:
    global _prune_thread
    thread = _prune_thread
    jlog(logger, event="session_prune_loop_stop_requested")
    _prune_stop.set()
    if thread and thread.is_alive():
        thread.join(timeout=5)
        if thread.is_alive():
            jlog(logger, level="WARN", event="session_prune_loop_stop_timeout")
        else:
            jlog(logger, event="session_prune_loop_joined")
    else:
        jlog(logger, event="session_prune_loop_not_running")
    _prune_thread = None


CHROMA_CONFIG = ChromaConfig(url=CHROMA_URL, collection_name=COLLECTION_NAME)
CHROMA_CLIENT: Optional[ChromaClient] = None
tb = ToolBridge(ALLOWED_DOMAINS)


async def reload_clients_from_options(
    options_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    global CURRENT_OPTIONS
    global LM_HOSTS, CHROMA_MODE, CHROMA_URL, COLLECTION_NAME
    global ALLOWED_DOMAINS, TEMP, TOP_P
    global AUTO_CONFIG_REQUESTED, UPSERTS_REQUESTED, AUTO_CONFIG_ACTIVE, UPSERTS_ACTIVE
    global CHROMA_CONFIG, CHROMA_CLIENT, HOST_POOL

    options = (
        options_override if options_override is not None else load_options_from_disk()
    )
    CURRENT_OPTIONS = options

    LM_HOSTS = _normalize_lm_hosts(options.get("lm_hosts", LM_HOSTS))
    requested_mode = str(options.get("chroma_mode", CHROMA_MODE)).lower()
    if requested_mode != "http":
        jlog(
            logger,
            level="WARN",
            event="chroma_mode_forced_http",
            requested=requested_mode,
        )
    CHROMA_MODE = "http"
    CHROMA_URL = options.get("chroma_url", CHROMA_URL)
    COLLECTION_NAME = options.get("collection_name", COLLECTION_NAME)
    ALLOWED_DOMAINS = options.get("allowed_domains", ALLOWED_DOMAINS)
    TEMP = float(options.get("temperature", TEMP))
    TOP_P = float(options.get("top_p", TOP_P))
    AUTO_CONFIG_REQUESTED = bool(options.get("auto_config", AUTO_CONFIG_REQUESTED))
    UPSERTS_REQUESTED = bool(options.get("upserts_enabled", UPSERTS_REQUESTED))

    tb.allowed_domains = set(ALLOWED_DOMAINS)

    HOST_POOL = HostPool(LM_HOSTS)

    CHROMA_CONFIG = ChromaConfig(url=CHROMA_URL, collection_name=COLLECTION_NAME)
    if CHROMA_CLIENT is not None:
        CHROMA_CLIENT.update_config(CHROMA_CONFIG)

    try:
        server = get_server()
        server.update_chroma(CHROMA_CLIENT)
        server.update_collection_name_provider(lambda: COLLECTION_NAME)
    except RuntimeError:
        pass

    client = APP_CLIENTS.get("lm")
    if client:
        await HOST_POOL.refresh(client)
    else:
        jlog(logger, level="WARN", event="hostpool_refresh_deferred")

    await update_bootstrap_state(force_refresh=False)

    logger.info("=== Cathedral Orchestrator reload ===")
    jlog(
        logger,
        event="orchestrator_reload",
        hosts=list(LM_HOSTS.values()),
        chroma_mode=CHROMA_MODE,
        chroma_url=CHROMA_URL,
        auto_config_requested=AUTO_CONFIG_REQUESTED,
        upserts_requested=UPSERTS_REQUESTED,
    )
    return options


def is_bootstrap_ready() -> bool:
    return BOOTSTRAP_EVENT.is_set()


def auto_config_enabled() -> bool:
    return AUTO_CONFIG_ACTIVE


def upserts_enabled() -> bool:
    return UPSERTS_ACTIVE


def get_collection_name() -> str:
    return COLLECTION_NAME


async def _catalog_provider() -> Dict[str, List[str]]:
    if HOST_POOL is None:
        return {}
    return await HOST_POOL.get_catalog()


async def update_bootstrap_state(
    force_refresh: bool = False,
    *,
    catalog_override: Optional[Dict[str, List[str]]] = None,
    chroma_ready_override: Optional[bool] = None,
) -> None:
    global AUTO_CONFIG_ACTIVE, UPSERTS_ACTIVE

    client = APP_CLIENTS.get("lm")
    catalog: Dict[str, List[str]] = {} if catalog_override is None else catalog_override
    if catalog_override is None and HOST_POOL is not None:
        if force_refresh and client:
            await HOST_POOL.refresh(client)
        catalog = await HOST_POOL.get_catalog()
    lm_ready = any(models for models in catalog.values())

    if chroma_ready_override is not None:
        chroma_ready = chroma_ready_override
    else:
        if CHROMA_URL and CHROMA_CLIENT is not None:
            chroma_ready = await CHROMA_CLIENT.health_ok()
        elif CHROMA_URL:
            chroma_ready = False
        else:
            chroma_ready = True

    ready = lm_ready and chroma_ready
    if ready:
        BOOTSTRAP_EVENT.set()
    else:
        BOOTSTRAP_EVENT.clear()

    AUTO_CONFIG_ACTIVE = ready and AUTO_CONFIG_REQUESTED
    UPSERTS_ACTIVE = ready and UPSERTS_REQUESTED
    jlog(
        logger,
        event="bootstrap_state",
        ready=ready,
        lm_ready=lm_ready,
        chroma_ready=chroma_ready,
        auto_config_active=AUTO_CONFIG_ACTIVE,
        upserts_active=UPSERTS_ACTIVE,
    )


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
    global CHROMA_CLIENT
    CHROMA_CLIENT = ChromaClient(APP_CLIENTS["chroma"], CHROMA_CONFIG)
    server = MPCServer(
        toolbridge=tb,
        chroma=CHROMA_CLIENT,
        catalog_provider=_catalog_provider,
        readiness_probe=is_bootstrap_ready,
        collection_name_provider=get_collection_name,
        upsert_allowed=upserts_enabled,
        auto_config_allowed=auto_config_enabled,
    )
    set_server(server)
    _start_pruner_if_needed()
    try:
        await reload_clients_from_options(dict(CURRENT_OPTIONS))
        await update_bootstrap_state(force_refresh=True)
        yield
    finally:
        stop_pruner()
        await asyncio.gather(*(client.aclose() for client in APP_CLIENTS.values()))
        APP_CLIENTS.clear()


app = FastAPI(title="Cathedral Orchestrator", lifespan=lifespan)
app.include_router(mpc_router, prefix="/mcp")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


@app.get("/health")
async def health():
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    if HOST_POOL is None or not HOST_POOL.has_hosts():
        raise HTTPException(status_code=503, detail="no lm hosts configured")

    hosts = HOST_POOL.list_hosts()
    if not hosts:
        raise HTTPException(status_code=503, detail="no lm hosts configured")

    catalog = await HOST_POOL.get_catalog()
    if not catalog:
        await HOST_POOL.refresh(client)
        catalog = await HOST_POOL.get_catalog()

    lm_counts = {base: len(models) for base, models in catalog.items()}
    lm_ready = any(count > 0 for count in lm_counts.values())
    chroma_ok = True
    if CHROMA_URL:
        chroma_ok = bool(CHROMA_CLIENT) and await CHROMA_CLIENT.health_ok()

    await update_bootstrap_state(
        force_refresh=False,
        catalog_override=catalog,
        chroma_ready_override=chroma_ok,
    )
    ready = lm_ready and chroma_ok
    status = 200 if ready else 503

    payload = {
        "ok": ready,
        "lm_hosts": lm_counts,
        "chroma": {"ok": chroma_ok},
    }
    if not ready:
        payload["detail"] = "bootstrap_pending"
    jlog(
        logger,
        event="health_status",
        host_count=len(lm_counts),
        chroma_ok=chroma_ok,
        ready=ready,
    )
    return JSONResponse(payload, status_code=status)


@app.get("/api/status")
async def api_status():
    if HOST_POOL is None or not HOST_POOL.is_ready():
        raise HTTPException(status_code=503, detail="host pool not ready")
    client = APP_CLIENTS.get("lm")
    if client and not (await HOST_POOL.get_catalog()):
        await HOST_POOL.refresh(client)
    catalog = await HOST_POOL.get_catalog()
    await update_bootstrap_state(force_refresh=False, catalog_override=catalog)
    sessions_active = await SESSION_MANAGER.list_active()
    options_snapshot = dict(CURRENT_OPTIONS)
    response = {
        "ok": True,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "sessions_active": sessions_active,
        "auto_config": AUTO_CONFIG_REQUESTED,
        "auto_config_active": AUTO_CONFIG_ACTIVE,
        "auto_discovery": bool(options_snapshot.get("auto_discovery", False)),
        "lock_hosts": bool(options_snapshot.get("lock_hosts", False)),
        "upserts_enabled": UPSERTS_REQUESTED,
        "upserts_active": UPSERTS_ACTIVE,
        "bootstrap_ready": BOOTSTRAP_EVENT.is_set(),
        "hosts": catalog,
    }
    jlog(
        logger,
        event="api_status",
        sessions=response["sessions_active"],
        host_count=len(catalog),
        bootstrap_ready=response["bootstrap_ready"],
    )
    return JSONResponse(response)


@app.get("/api/options")
async def api_options():
    async with OPTIONS_LOCK:
        options = load_options_from_disk()
    if options and options != CURRENT_OPTIONS:
        await reload_clients_from_options(dict(options))
    jlog(logger, event="api_options_get")
    return JSONResponse(options)


@app.post("/api/options")
async def api_set_options(request: Request):
    payload = await request.json()
    mutable_keys = {
        "auto_config",
        "auto_discovery",
        "lock_hosts",
        "lock_LMSTUDIO_BASE_PATH",
        "lock_EMBEDDING_BASE_PATH",
        "lock_CHROMA_URL",
        "lock_VECTOR_DB",
        "lm_hosts",
        "chroma_mode",
        "chroma_url",
        "chroma_persist_dir",
        "collection_name",
        "allowed_domains",
        "temperature",
        "top_p",
        "upserts_enabled",
    }
    bool_keys = {
        "auto_config",
        "auto_discovery",
        "lock_hosts",
        "lock_LMSTUDIO_BASE_PATH",
        "lock_EMBEDDING_BASE_PATH",
        "lock_CHROMA_URL",
        "lock_VECTOR_DB",
        "upserts_enabled",
    }

    updates: Dict[str, Any] = {}
    for key, value in payload.items():
        if key not in mutable_keys:
            continue
        if key in bool_keys:
            updates[key] = _coerce_bool(value)
        else:
            updates[key] = value

    if not updates:
        jlog(logger, level="INFO", event="api_options_noop")
        return JSONResponse({"ok": True, "updated": {}}, status_code=200)

    async with OPTIONS_LOCK:
        options = load_options_from_disk()
        options.update(updates)
        try:
            persist_options_to_disk(options)
        except Exception:
            return JSONResponse(
                {"ok": False, "error": "persist_failed"}, status_code=500
            )

    await reload_clients_from_options(dict(options))
    jlog(logger, event="api_options_updated", keys=list(updates.keys()))
    return JSONResponse({"ok": True, "options": options})


@app.get("/v1/models")
async def list_models():
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    if not LM_HOSTS:
        raise HTTPException(status_code=503, detail="no lm hosts configured")
    tasks = [list_models_from_host(client, base) for base in LM_HOSTS.values()]
    results = await asyncio.gather(*tasks)
    union: List[Dict[str, Any]] = []
    for base, models in results:
        for model in models:
            if "id" in model:
                union.append(model)
            elif "name" in model:
                merged = {
                    "id": model["name"],
                    **{k: v for k, v in model.items() if k != "name"},
                }
                union.append(merged)
    return JSONResponse({"object": "list", "data": union})


async def _route_for_model(model: str) -> str:
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    if not LM_HOSTS:
        raise HTTPException(status_code=503, detail="no lm hosts configured")
    tasks = [list_models_from_host(client, base) for base in LM_HOSTS.values()]
    results = await asyncio.gather(*tasks)
    index = build_model_index(results)
    try:
        return index[model]
    except KeyError:
        return list(LM_HOSTS.values())[0]


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model")
    target = await _route_for_model(model) if model else list(LM_HOSTS.values())[0]
    url = target.rstrip("/") + "/v1/chat/completions"
    stream = bool(body.get("stream", True))
    headers = {"Content-Type": "application/json"}
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    if stream:
        timeout = httpx.Timeout(connect=30, write=30, read=None, pool=None)
        async with client.stream(
            "POST", url, headers=headers, json=body, timeout=timeout
        ) as upstream:

            async def gen():
                async for chunk in upstream.aiter_raw():
                    yield chunk

            return await sse_proxy(gen())
    response = await client.post(url, headers=headers, json=body)
    return JSONResponse(response.json(), status_code=response.status_code)


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    body = await request.json()
    model = body.get("model")
    target = await _route_for_model(model) if model else list(LM_HOSTS.values())[0]
    url = target.rstrip("/") + "/v1/embeddings"
    headers = {"Content-Type": "application/json"}

    raw_input = body.get("input")
    if isinstance(raw_input, str):
        inputs_list = [raw_input]
    elif isinstance(raw_input, list):
        inputs_list = [
            x if isinstance(x, str) else (str(x) if x is not None else "")
            for x in raw_input
        ]
    else:
        inputs_list = []

    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    response = await client.post(url, headers=headers, json=body)
    response.raise_for_status()
    data = response.json()
    try:
        if UPSERTS_ACTIVE and CHROMA_CLIENT is not None:
            payload_items_raw = data.get("data")
            payload_items: List[Any]
            if isinstance(payload_items_raw, list):
                payload_items = payload_items_raw
            else:
                payload_items = []
            vectors: List[List[float]] = []
            for item in payload_items:
                if not isinstance(item, dict):
                    continue
                embedding = item.get("embedding")
                if isinstance(embedding, list):
                    vectors.append([float(v) for v in embedding])
            if not vectors:
                jlog(logger, event="chroma_upsert_skipped", reason="no_vectors")
            else:
                texts = inputs_list[: len(vectors)]
                if len(texts) < len(vectors):
                    texts.extend(["" for _ in range(len(vectors) - len(texts))])
                ids = [str(uuid.uuid4()) for _ in vectors]
                meta = body.get("metadata") or {}
                metadatas = [meta for _ in vectors]
                collection_id = await CHROMA_CLIENT.ensure_collection(COLLECTION_NAME)
                if collection_id:
                    ok = await CHROMA_CLIENT.upsert(
                        collection_id,
                        ids=ids,
                        documents=texts,
                        metadatas=metadatas,
                        embeddings=vectors,
                    )
                    jlog(
                        logger,
                        event="chroma_upsert",
                        result=ok,
                        count=len(vectors),
                    )
                else:
                    jlog(
                        logger,
                        level="ERROR",
                        event="chroma_collection_missing",
                        collection=COLLECTION_NAME,
                    )
    except Exception as exc:  # pragma: no cover - chroma guard
        jlog(logger, level="ERROR", event="chroma_upsert_fail", error=str(exc))
    return JSONResponse(data, status_code=response.status_code)
