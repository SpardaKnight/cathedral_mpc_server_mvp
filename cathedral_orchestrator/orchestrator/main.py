import asyncio
import json
import os
import uuid
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.responses import JSONResponse, Response
from starlette.responses import PlainTextResponse  # noqa: F401

from pydantic import BaseModel, Field, ValidationError

from . import sessions
from .logging_config import jlog, setup_logging
from .mpc_server import MPCServer, get_server, router as mpc_router, set_server
from .toolbridge import ToolBridge
from .vector.chroma_client import ChromaClient, ChromaConfig

logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

APP_CLIENTS: Dict[str, httpx.AsyncClient] = {}
OPTIONS_PATH = Path(os.environ.get("CATHEDRAL_OPTIONS_PATH", "/data/options.json"))
OPTIONS_LOCK = asyncio.Lock()

# Cache of upstream model object payloads (as returned by LM Studio/OpenAI style)
MODEL_OBJECTS: Dict[str, List[Dict[str, Any]]] = {}


def _normalize_lm_hosts(raw: Any) -> Dict[str, str]:
    """
    Accepts list[str] or dict[str,str]; returns dict of clean base URLs without '/v1'.
    Ensures no trailing slash so later joins of '/v1/...' are correct.
    """
    result: Dict[str, str] = {}
    if isinstance(raw, dict):
        items = list(raw.items())
    else:
        seq = list(raw or [])
        items = [(str(i), str(i)) for i in seq]
    for key, url in items:
        if not url:
            continue
        base = str(url).strip().rstrip("/")
        if base.lower().endswith("/v1"):
            base = base[:-3]  # strip '/v1'
        result[str(key)] = base
    return result


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
async def list_models_from_host(client: httpx.AsyncClient, base: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Query <base>/v1/models and return the raw 'data' list items unmodified.
    This preserves LM Studio metadata (e.g., context_length) for UI auto-detection.
    """
    base_clean = base.rstrip("/")
    url = f"{base_clean}/v1/models"
    resp = await client.get(
        url,
        headers={"Accept": "application/json"},
        follow_redirects=True,
        timeout=httpx.Timeout(connect=10, read=20),
    )
    resp.raise_for_status()
    payload = resp.json()
    items: List[Dict[str, Any]] = []
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        for it in payload["data"]:
            if isinstance(it, dict):
                items.append(dict(it))
            elif isinstance(it, str):
                items.append({"id": str(it), "object": "model"})
    jlog(
        logger,
        level="DEBUG",
        event="lm_models_fetched",
        host=base_clean,
        models=len(items),
    )
    return base_clean, items


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
        try:
            if not self._hosts:
                async with self._lock:
                    self._catalog = {}
                jlog(logger, level="DEBUG", event="hostpool_refresh", hosts=0)
                return {}

            bases = list(self._hosts.values())
            tasks = [list_models_from_host(client, base) for base in bases]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            catalog: Dict[str, List[Dict[str, Any]]] = {}
            for base, result in zip(bases, results):
                base_key = base.rstrip("/")
                if isinstance(result, BaseException):
                    catalog[base_key] = []
                    jlog(
                        logger,
                        level="WARN",
                        event="hostpool_refresh_failed",
                        host=base_key,
                        error=str(result),
                    )
                    continue
                real_base, models = cast(Tuple[str, List[Dict[str, Any]]], result)
                catalog[real_base.rstrip("/")] = models
            async with self._lock:
                self._catalog = catalog
            counts = {base: len(models) for base, models in catalog.items()}
            jlog(logger, event="hostpool_refreshed", counts=counts)
            return catalog
        except Exception as exc:
            jlog(logger, level="WARN", event="hostpool_refresh_failed", error=str(exc))
            async with self._lock:
                self._catalog = {}
            return {}

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


class OptionsModel(BaseModel):
    lm_hosts: List[str] = Field(default_factory=list)
    chroma_mode: str = "http"
    chroma_url: Optional[str] = None
    chroma_persist_dir: Optional[str] = None
    collection_name: str = "cathedral"
    allowed_domains: List[str] = Field(
        default_factory=lambda: ["light", "switch", "scene"]
    )
    temperature: float = 0.7
    top_p: float = 0.9
    upserts_enabled: bool = True
    auto_config: bool = True
    auto_discovery: bool = False
    lock_hosts: bool = False
    lock_LMSTUDIO_BASE_PATH: bool = False
    lock_EMBEDDING_BASE_PATH: bool = False
    lock_CHROMA_URL: bool = False
    lock_VECTOR_DB: bool = False
    auto_config_active: bool = False
    upserts_active: bool = False


DEFAULT_OPTIONS = OptionsModel().model_dump()

CURRENT_OPTIONS = load_options_from_disk()
if CURRENT_OPTIONS:
    merged = {**DEFAULT_OPTIONS, **CURRENT_OPTIONS}
    CURRENT_OPTIONS = OptionsModel(**merged).model_dump()
else:
    CURRENT_OPTIONS = dict(DEFAULT_OPTIONS)

LM_HOSTS: Dict[str, str] = _normalize_lm_hosts(CURRENT_OPTIONS.get("lm_hosts"))
CURRENT_OPTIONS["lm_hosts"] = list(LM_HOSTS.values())
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
MODEL_CATALOG: Dict[str, List[str]] = {}
HOST_HEALTH: Dict[str, str] = {}

# --- session prune loop (idempotent) -----------------------------------------
_prune_thread: Optional[threading.Thread] = None
_prune_stop = threading.Event()


def _prune_loop() -> None:
    jlog(
        logger,
        event="session_prune_loop_started",
        ttl_minutes=sessions.DEFAULT_TTL_MINUTES,
        interval_seconds=sessions.DEFAULT_PRUNE_INTERVAL_SECONDS,
    )
    try:
        while not _prune_stop.is_set():
            try:
                pruned = sessions.prune_expired_sync()
                jlog(
                    logger,
                    event="session_prune_cycle",
                    pruned=int(pruned),
                    ttl_minutes=sessions.DEFAULT_TTL_MINUTES,
                )
            except Exception as exc:  # defensive
                jlog(
                    logger,
                    level="ERROR",
                    event="session_prune_failed",
                    ttl_minutes=sessions.DEFAULT_TTL_MINUTES,
                    error=str(exc),
                )
            _prune_stop.wait(sessions.DEFAULT_PRUNE_INTERVAL_SECONDS)
    finally:
        jlog(logger, event="session_prune_loop_stopped")


def start_pruner() -> None:
    global _prune_thread
    if _prune_thread and _prune_thread.is_alive():
        jlog(logger, event="session_prune_loop_already_running")
        return
    _prune_stop.clear()
    _prune_thread = threading.Thread(
        target=_prune_loop,
        name="cathedral-session-pruner",
        daemon=True,
    )
    _prune_thread.start()
    jlog(logger, event="session_prune_loop_spawned")


def stop_pruner() -> None:
    global _prune_thread
    if _prune_thread and _prune_thread.is_alive():
        _prune_stop.set()
        _prune_thread.join(timeout=5)
        jlog(logger, event="session_prune_loop_joined")
    else:
        jlog(logger, event="session_prune_loop_not_running")
    _prune_thread = None
    _prune_stop.clear()


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
    CURRENT_OPTIONS.setdefault("auto_config_active", AUTO_CONFIG_ACTIVE)
    CURRENT_OPTIONS.setdefault("upserts_active", UPSERTS_ACTIVE)

    LM_HOSTS = _normalize_lm_hosts(options.get("lm_hosts", LM_HOSTS))
    CURRENT_OPTIONS["lm_hosts"] = list(LM_HOSTS.values())
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
    chroma_http = APP_CLIENTS.get("chroma")
    if chroma_http is not None:
        CHROMA_CLIENT = ChromaClient(chroma_http, CHROMA_CONFIG)

    try:
        server = get_server()
        server.update_chroma(CHROMA_CLIENT)
        server.update_collection_name_provider(lambda: COLLECTION_NAME)
    except RuntimeError:
        pass

    if CHROMA_CLIENT is not None and CHROMA_MODE == "http":
        try:
            await CHROMA_CLIENT.ensure_collection(COLLECTION_NAME)
        except Exception as exc:  # pragma: no cover - chroma guard
            jlog(
                logger,
                level="WARN",
                event="chroma_collection_bootstrap_failed",
                error=str(exc),
                collection=COLLECTION_NAME,
            )

    client = APP_CLIENTS.get("lm")
    if client:
        await HOST_POOL.refresh(client)
    else:
        jlog(logger, level="WARN", event="hostpool_refresh_deferred")

    await update_bootstrap_state(force_refresh=False)

    try:
        await _refresh_model_catalog()
    except Exception as exc:  # pragma: no cover - defensive guard
        jlog(
            logger,
            level="WARN",
            event="model_catalog_refresh_failed",
            error=str(exc),
        )

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


async def _refresh_model_catalog() -> None:
    """
    Populate both:
      - MODEL_CATALOG: {host: [id, ...]}
      - MODEL_OBJECTS: {host: [<raw model dict>, ...]}
    keeping host health in sync.
    """
    global MODEL_CATALOG, MODEL_OBJECTS, HOST_HEALTH
    hosts = [host.rstrip("/") for host in LM_HOSTS.values()]
    if not hosts:
        MODEL_CATALOG = {}
        MODEL_OBJECTS = {}
        HOST_HEALTH = {}
        jlog(logger, event="model_catalog_empty")
        return
    client = APP_CLIENTS.get("lm")
    if client is None:
        jlog(logger, level="WARN", event="model_catalog_client_missing")
        return
    tasks = [list_models_from_host(client, host) for host in hosts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    new_ids: Dict[str, List[str]] = {}
    new_objs: Dict[str, List[Dict[str, Any]]] = {}
    health: Dict[str, str] = {}

    for host, result in zip(hosts, results):
        if isinstance(result, BaseException):
            new_ids[host] = []
            new_objs[host] = []
            health[host] = "down"
            jlog(logger, level="WARN", event="model_catalog_gather_failed", host=host, error=str(result))
            continue
        base, payload = cast(Tuple[str, List[Dict[str, Any]]], result)
        clean = base.rstrip("/")
        # Trust upstream objects; derive ids for routing
        obj_list: List[Dict[str, Any]] = [obj for obj in payload if isinstance(obj, dict)]
        ids = [str(obj.get("id") or obj.get("name")) for obj in obj_list if (obj.get("id") or obj.get("name"))]
        new_objs[clean] = obj_list
        new_ids[clean] = ids
        health[clean] = "ok" if ids else "down"
        jlog(logger, event="model_catalog_host", host=clean, models=len(ids), status=health[clean])

    MODEL_CATALOG = new_ids
    MODEL_OBJECTS = new_objs
    HOST_HEALTH = health
    jlog(logger, event="model_catalog_refreshed", hosts=len(MODEL_CATALOG))


# --- bootstrap loop -----------------------------------------------------------
async def _bootstrap_loop(interval_seconds: int = 30) -> None:
    while True:
        try:
            await reload_clients_from_options(dict(CURRENT_OPTIONS))
            await update_bootstrap_state(force_refresh=True)
        except Exception as exc:
            jlog(logger, level="WARN", event="bootstrap_loop_error", error=str(exc))
        try:
            await asyncio.sleep(interval_seconds)
        except Exception:
            pass


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
    global AUTO_CONFIG_ACTIVE, UPSERTS_ACTIVE, CURRENT_OPTIONS

    client = APP_CLIENTS.get("lm")
    catalog: Dict[str, List[str]] = {}
    if catalog_override is not None:
        catalog = catalog_override
    elif HOST_POOL is not None:
        if force_refresh and client:
            try:
                await HOST_POOL.refresh(client)
            except Exception as exc:
                jlog(
                    logger,
                    level="WARN",
                    event="bootstrap_state_hostpool_refresh_failed",
                    error=str(exc),
                )
        try:
            catalog = await HOST_POOL.get_catalog()
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="bootstrap_state_catalog_failed",
                error=str(exc),
            )
    lm_ready = any(models for models in catalog.values())

    if chroma_ready_override is not None:
        chroma_ready = chroma_ready_override
    else:
        try:
            if CHROMA_URL and CHROMA_CLIENT is not None:
                chroma_ready = await CHROMA_CLIENT.health()
            elif CHROMA_URL:
                chroma_ready = False
            else:
                chroma_ready = True
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="bootstrap_state_chroma_failed",
                error=str(exc),
            )
            chroma_ready = False

    ready = lm_ready and chroma_ready
    if ready:
        BOOTSTRAP_EVENT.set()
    else:
        BOOTSTRAP_EVENT.clear()

    AUTO_CONFIG_ACTIVE = ready and AUTO_CONFIG_REQUESTED
    UPSERTS_ACTIVE = ready and UPSERTS_REQUESTED
    CURRENT_OPTIONS["auto_config_active"] = AUTO_CONFIG_ACTIVE
    CURRENT_OPTIONS["upserts_active"] = UPSERTS_ACTIVE
    jlog(
        logger,
        event="bootstrap_state",
        ready=ready,
        lm_ready=lm_ready,
        chroma_ready=chroma_ready,
        auto_config_active=AUTO_CONFIG_ACTIVE,
        upserts_active=UPSERTS_ACTIVE,
    )


async def get_readiness() -> Tuple[bool, bool, bool]:
    catalog_snapshot = dict(MODEL_CATALOG)
    lm_ready = any(models for models in catalog_snapshot.values())
    if CHROMA_URL and CHROMA_CLIENT is not None:
        chroma_ready = await CHROMA_CLIENT.health()
    elif CHROMA_URL:
        chroma_ready = False
    else:
        chroma_ready = True
    ready = lm_ready and chroma_ready
    await update_bootstrap_state(
        force_refresh=False,
        catalog_override=catalog_snapshot if catalog_snapshot else None,
        chroma_ready_override=chroma_ready,
    )
    jlog(
        logger,
        event="readiness_snapshot",
        ready=ready,
        lm_ready=lm_ready,
        chroma_ready=chroma_ready,
    )
    return ready, lm_ready, chroma_ready


@asynccontextmanager
async def lifespan(app: FastAPI):
    APP_CLIENTS["lm"] = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=5, read=5, write=10, pool=None),
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
    start_pruner()
    try:
        asyncio.create_task(_bootstrap_loop(interval_seconds=30))
        yield
    finally:
        stop_pruner()
        await asyncio.gather(*(client.aclose() for client in APP_CLIENTS.values()))
        APP_CLIENTS.clear()


app = FastAPI(title="Cathedral Orchestrator", lifespan=lifespan)
app.include_router(mpc_router, prefix="/mcp")
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
        chroma_ok = bool(CHROMA_CLIENT) and await CHROMA_CLIENT.health()

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
async def api_status() -> JSONResponse:
    await _refresh_model_catalog()
    ready, lm_ready, chroma_ready = await get_readiness()
    sessions_active = await SESSION_MANAGER.list_active()
    options_snapshot = dict(CURRENT_OPTIONS)
    catalog_snapshot = dict(MODEL_CATALOG)
    host_health_snapshot = dict(HOST_HEALTH)
    response = {
        "ok": ready,
        "lm_ready": lm_ready,
        "chroma_ready": chroma_ready,
        "sessions_active": sessions_active,
        "catalog": catalog_snapshot,
        "host_health": host_health_snapshot,
        "auto_config_requested": bool(
            options_snapshot.get("auto_config", AUTO_CONFIG_REQUESTED)
        ),
        "auto_config_active": AUTO_CONFIG_ACTIVE,
        "upserts_enabled": bool(options_snapshot.get("upserts_enabled", True)),
        "upserts_active": UPSERTS_ACTIVE,
        "auto_discovery": bool(options_snapshot.get("auto_discovery", False)),
        "lock_hosts": bool(options_snapshot.get("lock_hosts", False)),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    jlog(
        logger,
        event="api_status",
        sessions=response["sessions_active"],
        host_count=len(catalog_snapshot),
        ready=ready,
        lm_ready=lm_ready,
        chroma_ready=chroma_ready,
    )
    return JSONResponse(response)


@app.get("/api/options")
async def api_options() -> JSONResponse:
    jlog(logger, event="api_options_get")
    return JSONResponse(dict(CURRENT_OPTIONS))


@app.post("/api/options")
async def api_set_options(request: Request) -> JSONResponse:
    body = await request.json()
    if not isinstance(body, dict):
        jlog(logger, level="ERROR", event="api_options_invalid_payload")
        return JSONResponse({"ok": False, "error": "invalid_payload"}, status_code=400)
    lock_map = {
        "lm_hosts": bool(CURRENT_OPTIONS.get("lock_hosts", False)),
        "chroma_url": bool(CURRENT_OPTIONS.get("lock_CHROMA_URL", False)),
        "chroma_mode": bool(CURRENT_OPTIONS.get("lock_VECTOR_DB", False)),
    }

    status_fields = {"auto_config_active", "upserts_active"}
    filtered_body: Dict[str, Any] = {}
    for key, value in body.items():
        if key in status_fields:
            jlog(
                logger,
                level="INFO",
                event="api_options_status_field_ignored",
                field=key,
            )
            continue
        if key in lock_map and lock_map[key]:
            jlog(
                logger,
                level="WARN",
                event="api_options_locked_field",
                field=key,
            )
            continue
        if key == "lm_hosts":
            filtered_body[key] = list(_normalize_lm_hosts(value).values())
        else:
            filtered_body[key] = value

    merged = {**DEFAULT_OPTIONS, **CURRENT_OPTIONS, **filtered_body}
    try:
        validated = OptionsModel.model_validate(merged)
    except ValidationError as exc:
        jlog(
            logger,
            level="ERROR",
            event="api_options_validation_failed",
            error=str(exc),
        )
        return JSONResponse({"ok": False, "error": "validation_failed"}, status_code=400)
    payload = dict(validated.model_dump())
    async with OPTIONS_LOCK:
        try:
            persist_options_to_disk(payload)
        except Exception:
            jlog(
                logger,
                level="ERROR",
                event="api_options_persist_failed",
            )
            return JSONResponse(
                {"ok": False, "error": "persist_failed"}, status_code=500
            )
    await reload_clients_from_options(dict(payload))
    await update_bootstrap_state(force_refresh=True)
    jlog(logger, event="api_options_updated", keys=list(payload.keys()))
    return JSONResponse({"ok": True, "options": dict(CURRENT_OPTIONS)})


@app.get("/v1/models")
async def models_v1(_request: Request) -> JSONResponse:
    """
    Union of upstream model OBJECTS, not just ids.
    Preserve all fields so clients (AnythingLLM) can auto-detect context window.
    """
    # Snapshot to avoid mutation during iteration
    objs = dict(MODEL_OBJECTS)
    union: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for items in objs.values():
        for obj in items:
            mid = str(obj.get("id") or obj.get("name") or "")
            if not mid or mid in seen:
                continue
            seen.add(mid)
            # Do not mutate upstream payload; shallow copy in case we annotate later
            union.append(dict(obj))
    return JSONResponse({"object": "list", "data": union})


@app.get("/api/v0/models")
async def models_v0_aggregate(_request: Request):
    """
    Provide a REST-style model inventory compatible with LM Studio's /api/v0/models,
    unioned across configured hosts. If exactly one host is configured, we pass through.
    """
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    hosts = list(LM_HOSTS.values())
    if not hosts:
        return JSONResponse({"loaded": [], "downloaded": []})

    if len(hosts) == 1:
        url = hosts[0].rstrip("/") + "/api/v0/models"
        try:
            resp = await client.get(url, follow_redirects=True, timeout=20)
            resp.raise_for_status()
            payload = resp.json()
            jlog(
                logger,
                event="models_v0_passthrough",
                host=hosts[0].rstrip("/"),
            )
            return JSONResponse(payload)
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="models_v0_passthrough_failed",
                host=hosts[0].rstrip("/"),
                error=str(exc),
            )

    loaded: List[Dict[str, Any]] = []
    catalog = await _catalog_provider()
    objects_snapshot = {host: list(objs) for host, objs in MODEL_OBJECTS.items()}
    for host, models in catalog.items():
        host_key = host.rstrip("/")
        obj_index: Dict[str, Dict[str, Any]] = {}
        for raw_obj in objects_snapshot.get(host_key, []):
            if isinstance(raw_obj, dict):
                mid = raw_obj.get("id") or raw_obj.get("name")
                if mid:
                    obj_index[str(mid)] = raw_obj
        for mid in models:
            item: Dict[str, Any] = {
                "name": mid,
                "state": "loaded",
                "provider": "upstream",
            }
            obj_data = obj_index.get(mid)
            if isinstance(obj_data, dict):
                if "context_length" in obj_data:
                    item["context_length"] = int(obj_data["context_length"])
                    item["max_context_length"] = int(obj_data["context_length"])
                if "max_context_length" in obj_data and "max_context_length" not in item:
                    try:
                        item["max_context_length"] = int(obj_data["max_context_length"])
                    except (TypeError, ValueError):
                        pass
                if "embedding_length" in obj_data:
                    try:
                        item["embedding_length"] = int(obj_data["embedding_length"])
                    except (TypeError, ValueError):
                        pass
            loaded.append(item)
    jlog(
        logger,
        event="models_v0_union",
        hosts=len(catalog),
        loaded=len(loaded),
    )
    return JSONResponse({"loaded": loaded, "downloaded": []})


@app.head("/v1/models")
async def models_v1_head() -> Response:
    """
    Lightweight provider probe. Return 200 if at least one LM host responds to /v1/models.
    """
    if not LM_HOSTS:
        raise HTTPException(status_code=503, detail="no lm hosts configured")
    client = APP_CLIENTS.get("lm")
    if client is None:
        raise HTTPException(status_code=503, detail="client not ready")
    for base in LM_HOSTS.values():
        try:
            host = base.rstrip("/")
            resp = await client.get(f"{host}/v1/models", timeout=5)
            if resp.status_code == 200:
                jlog(logger, event="models_v1_head_ok", host=host)
                return Response(status_code=200)
            jlog(
                logger,
                level="DEBUG",
                event="models_v1_head_non_200",
                host=host,
                status=int(resp.status_code),
            )
        except Exception as exc:
            jlog(
                logger,
                level="WARN",
                event="models_v1_head_failed",
                host=base.rstrip("/"),
                error=str(exc),
            )
            continue
    jlog(logger, level="WARN", event="models_v1_head_unavailable")
    raise HTTPException(status_code=503, detail="no upstream models endpoint")


async def _route_for_model(model: str) -> str:
    client = APP_CLIENTS.get("lm")
    if not client:
        raise HTTPException(status_code=503, detail="client not ready")
    if not LM_HOSTS:
        raise HTTPException(status_code=503, detail="no lm hosts configured")
    bases = list(LM_HOSTS.values())
    tasks = [list_models_from_host(client, base) for base in bases]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    filtered: List[Tuple[str, List[Dict[str, Any]]]] = []
    for base, result in zip(bases, results):
        if isinstance(result, BaseException):
            jlog(
                logger,
                level="WARN",
                event="route_for_model_failed",
                host=base.rstrip("/"),
                error=str(result),
            )
            continue
        filtered.append(cast(Tuple[str, List[Dict[str, Any]]], result))
    index = build_model_index(filtered)
    try:
        return index[model]
    except KeyError:
        return list(LM_HOSTS.values())[0]


@app.post("/v1/chat/completions")
async def relay_chat_completions(request: Request):
    if not LM_HOSTS:
        raise HTTPException(status_code=503, detail="no lm hosts configured")

    body_bytes = await request.body()
    model: Optional[str] = None
    if body_bytes:
        try:
            payload = json.loads(body_bytes)
            if isinstance(payload, dict):
                model = payload.get("model")
        except Exception:
            model = None

    target_base = await _route_for_model(model) if model else list(LM_HOSTS.values())[0]
    url = f"{target_base.rstrip('/')}/v1/chat/completions"

    fwd_headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
    auth = request.headers.get("authorization")
    if auth:
        fwd_headers["Authorization"] = auth

    async def stream_sse():
        saw_done = False
        started = False
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, headers=fwd_headers, content=body_bytes) as upstream:
                    async for chunk in upstream.aiter_raw():
                        if await request.is_disconnected():
                            jlog(logger, event="chat_relay_client_disconnected", url=url)
                            break
                        if chunk:
                            if b"[DONE]" in chunk:
                                saw_done = True
                            started = True
                            yield chunk
        except httpx.StreamClosed:
            # Clean EOF from upstream
            pass
        except httpx.HTTPError as exc:
            jlog(logger, level="ERROR", event="chat_relay_upstream_error", url=url, error=str(exc))
            if not started:
                # Only error before any bytes were streamed
                raise HTTPException(status_code=502, detail="upstream_http_error") from exc
        finally:
            if not saw_done and not await request.is_disconnected():
                # OpenAI-style terminator
                yield b"data: [DONE]\n\n"

    return StreamingResponse(stream_sse(), media_type="text/event-stream")


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
