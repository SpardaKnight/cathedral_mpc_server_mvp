from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import sessions
from .logging_config import jlog, setup_logging
from .toolbridge import ToolBridge
from .vector.chroma_client import ChromaClient

router = APIRouter()

logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))


class MPCServer:
    def __init__(
        self,
        toolbridge: ToolBridge,
        chroma: Optional[ChromaClient],
        *,
        catalog_provider: Callable[[], Awaitable[Dict[str, List[str]]]],
        readiness_probe: Callable[[], bool],
        collection_name_provider: Callable[[], str],
        upsert_allowed: Callable[[], bool],
        auto_config_allowed: Callable[[], bool],
    ):
        self.tb = toolbridge
        self.chroma = chroma
        self._catalog_provider = catalog_provider
        self._readiness_probe = readiness_probe
        self._collection_name_provider = collection_name_provider
        self._upsert_allowed = upsert_allowed
        self._auto_config_allowed = auto_config_allowed

    def update_chroma(self, chroma: Optional[ChromaClient]) -> None:
        self.chroma = chroma
        jlog(logger, event="mpc_server_update_chroma", available=bool(chroma))

    def update_collection_name_provider(
        self, provider: Callable[[], str]
    ) -> None:
        self._collection_name_provider = provider
        jlog(logger, event="mpc_server_update_collection_provider")

    async def catalog_snapshot(self) -> Dict[str, List[str]]:
        catalog = await self._catalog_provider()
        jlog(
            logger,
            event="mpc_server_catalog_snapshot",
            hosts=len(catalog),
        )
        return catalog

    def is_ready(self) -> bool:
        ready = self._readiness_probe()
        jlog(logger, event="mpc_server_ready_state", ready=ready)
        return ready

    def auto_config_allowed(self) -> bool:
        allowed = self._auto_config_allowed()
        jlog(logger, event="mpc_server_auto_config_state", allowed=allowed)
        return allowed

    async def handle(self, ws: WebSocket):
        await ws.accept()
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                scope = msg.get("scope")
                rid = msg.get("id") or str(uuid.uuid4())
                try:
                    if scope and scope.startswith("tools."):
                        res = await self._handle_tools(msg)
                    elif scope and scope.startswith("session."):
                        res = await self._handle_session(msg)
                    elif scope and scope.startswith("memory."):
                        res = await self._handle_memory(msg)
                    elif scope and scope.startswith(
                        (
                            "config.",
                            "prompts.",
                            "sampling.",
                            "resources.",
                            "agents.",
                            "cathedral.",
                        )
                    ):
                        res = await self._handle_generic(msg)
                    else:
                        res = {"ok": False, "error": "unknown_scope"}
                except Exception as exc:  # pragma: no cover - ws guard
                    jlog(
                        logger,
                        level="ERROR",
                        event="mpc_server_handle_error",
                        scope=scope,
                        error=str(exc),
                    )
                    res = {"ok": False, "error": str(exc)}
                frame = {"id": rid, "scope": scope, "response": res, "ts": time.time()}
                await ws.send_text(json.dumps(frame))
        except WebSocketDisconnect:
            return

    async def _handle_tools(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        tool = msg.get("tool")
        if not isinstance(tool, str) or not tool:
            jlog(logger, level="ERROR", event="mpc_tools_invalid", payload=msg)
            return {"ok": False, "error": "invalid_tool_name"}
        payload = msg.get("payload") or {}
        result = await self.tb.call(tool, payload)
        jlog(logger, event="mpc_tools_called", tool=tool, ok=bool(result.get("ok")))
        return result

    async def _handle_session(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        action = msg.get("action")
        workspace_id = msg.get("workspace_id") or "default"
        if action == "create":
            conversation_id = msg.get("conversation_id")
            user_id = msg.get("user_id")
            persona_id = msg.get("persona_id")
            thread_id = msg.get("thread_id") or f"thr_{int(time.time()*1000):x}"
            await sessions.upsert_session(
                workspace_id,
                thread_id,
                conversation_id=conversation_id,
                user_id=user_id,
                persona_id=persona_id,
            )
            session = await sessions.get_session(workspace_id, thread_id)
            jlog(
                logger,
                event="mpc_session_created",
                workspace_id=workspace_id,
                thread_id=thread_id,
            )
            return {"ok": True, "thread_id": thread_id, "session": session}
        if action == "resume":
            thread_id = msg.get("thread_id")
            if not thread_id:
                jlog(logger, level="ERROR", event="mpc_session_resume_missing")
                return {"ok": False, "error": "thread_id_required"}
            row = await sessions.get_session(workspace_id, thread_id)
            if row:
                await sessions.touch_session(workspace_id, thread_id)
            jlog(
                logger,
                event="mpc_session_resumed",
                workspace_id=workspace_id,
                thread_id=thread_id,
                found=bool(row),
            )
            return {"ok": bool(row), "session": row}
        jlog(logger, level="ERROR", event="mpc_session_unknown_action", action=action)
        return {"ok": False, "error": "unknown_session_action"}

    async def _handle_memory(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        if not self._upsert_allowed():
            jlog(logger, event="mpc_memory_upserts_disabled")
            return {"ok": False, "error": "upserts_disabled"}
        if self.chroma is None:
            jlog(logger, level="ERROR", event="mpc_memory_no_chroma")
            return {"ok": False, "error": "chroma_unavailable"}
        workspace_id = msg.get("workspace_id") or "default"
        thread_id = msg.get("thread_id")
        if not thread_id:
            jlog(logger, level="ERROR", event="mpc_memory_missing_thread")
            return {"ok": False, "error": "thread_id_required"}
        session = await sessions.get_session(workspace_id, thread_id)
        if not session:
            jlog(
                logger,
                level="ERROR",
                event="mpc_memory_session_missing",
                workspace_id=workspace_id,
                thread_id=thread_id,
            )
            return {"ok": False, "error": "session_missing"}
        collection_name = session.get("chroma_collection_name") or self._collection_name_provider()
        collection_id = session.get("chroma_collection_id")
        if not collection_id:
            collection_id = await self.chroma.ensure_collection(collection_name)
            if not collection_id:
                jlog(
                    logger,
                    level="ERROR",
                    event="mpc_memory_collection_error",
                    workspace_id=workspace_id,
                    thread_id=thread_id,
                    collection=collection_name,
                )
                return {"ok": False, "error": "collection_unavailable"}
            await sessions.set_collection(
                workspace_id,
                thread_id,
                collection_name,
                collection_id,
            )
            jlog(
                logger,
                event="mpc_memory_collection_linked",
                workspace_id=workspace_id,
                thread_id=thread_id,
                collection=collection_name,
                collection_id=collection_id,
            )
        ids = msg.get("ids") or []
        documents = msg.get("documents") or []
        metadatas = msg.get("metadatas") or []
        embeddings = msg.get("embeddings")
        if not metadatas:
            metadatas = [{} for _ in documents]
        ok = await self.chroma.upsert(
            collection_id,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        if ok:
            jlog(
                logger,
                event="mpc_memory_upsert_ok",
                workspace_id=workspace_id,
                thread_id=thread_id,
                count=len(ids),
            )
            return {"ok": True, "collection_id": collection_id}
        jlog(
            logger,
            level="ERROR",
            event="mpc_memory_upsert_failed",
            workspace_id=workspace_id,
            thread_id=thread_id,
        )
        return {"ok": False, "error": "upsert_failed"}

    async def _handle_generic(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        payload = msg.get("payload", {})
        jlog(logger, event="mpc_generic_echo", scope=msg.get("scope"))
        return {"ok": True, "echo": payload}


mpc_server_singleton: Optional[MPCServer] = None


def get_server() -> MPCServer:
    global mpc_server_singleton
    if mpc_server_singleton is None:
        raise RuntimeError("MPC server not initialized")
    return mpc_server_singleton


def set_server(server: MPCServer) -> None:
    global mpc_server_singleton
    mpc_server_singleton = server


@router.websocket("/")
async def mcp_socket(ws: WebSocket):
    await ws.accept()
    server = get_server()
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            typ = msg.get("type")
            scope = msg.get("scope")
            rid = msg.get("id") or str(uuid.uuid4())
            headers = msg.get("headers") or {}
            body = msg.get("body") or {}
            legacy = typ is None

            if legacy:
                payload = msg
            else:
                payload = {**(body if isinstance(body, dict) else {})}
                if headers.get("workspace_id"):
                    payload.setdefault("workspace_id", headers["workspace_id"])

            if scope == "handshake":
                res = {
                    "server": "cathedral-mpc/1.0",
                    "scopes": {
                        "handled": [
                            "session.*",
                            "memory.*",
                            "prompts.*",
                            "config.*",
                            "sampling.*",
                            "resources.*",
                            "agents.*",
                            "cathedral.*",
                        ],
                        "delegated": ["tools.*"],
                    },
                    "heartbeat_ms": 30000,
                }
                frame = {"id": rid, "type": "mcp.response", "ok": True, "body": res}
            elif scope and scope.startswith("tools."):
                tool = body.get("intent") if not legacy else msg.get("tool")
                if not tool:
                    tool = msg.get("tool") or payload.get("tool")
                args = (
                    (body.get("args") if not legacy else msg.get("payload"))
                    or payload.get("payload")
                    or {}
                )
                res = await server._handle_tools({"tool": tool, "payload": args})
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": bool(res.get("ok")),
                    "body": res,
                }
            elif scope and scope.startswith("session."):
                call = payload if legacy else payload
                res = await server._handle_session(call)
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": bool(res.get("ok")),
                    "body": res,
                }
            elif scope == "config.read.result":
                if not server.is_ready() or not server.auto_config_allowed():
                    frame = {
                        "id": rid,
                        "type": "mcp.response",
                        "ok": False,
                        "error": {"code": "BOOTSTRAP_PENDING"},
                    }
                else:
                    envmap = body if not legacy else msg.get("payload") or {}
                    updates: Dict[str, Any] = {}
                    if isinstance(envmap, dict):
                        if envmap.get("LMSTUDIO_BASE_PATH"):
                            updates["lm_hosts"] = [envmap["LMSTUDIO_BASE_PATH"]]
                        if envmap.get("CHROMA_URL"):
                            updates["chroma_mode"] = "http"
                            updates["chroma_url"] = envmap["CHROMA_URL"]
                    if updates:
                        try:
                            async with httpx.AsyncClient(timeout=10) as client:
                                r = await client.post(
                                    "http://127.0.0.1:8001/api/options", json=updates
                                )
                                ok = r.status_code == 200
                                frame = {
                                    "id": rid,
                                    "type": "mcp.response",
                                    "ok": ok,
                                    "body": {"applied": updates},
                                }
                                jlog(
                                    logger,
                                    event="mpc_config_applied",
                                    ok=ok,
                                    keys=list(updates.keys()),
                                )
                        except Exception as exc:  # pragma: no cover - network guard
                            frame = {
                                "id": rid,
                                "type": "mcp.response",
                                "ok": False,
                                "error": {"code": "APPLY_FAIL", "message": str(exc)},
                            }
                            jlog(
                                logger,
                                level="ERROR",
                                event="mpc_config_apply_failed",
                                error=str(exc),
                            )
                    else:
                        frame = {
                            "id": rid,
                            "type": "mcp.response",
                            "ok": True,
                            "body": {"applied": {}},
                        }
            elif scope and scope.startswith("memory."):
                call = payload if legacy else payload
                res = await server._handle_memory(call)
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": bool(res.get("ok", True)),
                    "body": res,
                }
            elif scope == "resources.list":
                catalog = await server.catalog_snapshot()
                resources: List[Dict[str, Any]] = []
                for host, models in catalog.items():
                    for model_id in models:
                        resources.append({"id": model_id, "host": host})
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": True,
                    "body": {"resources": resources},
                }
                jlog(
                    logger,
                    event="mpc_resources_list",
                    count=len(resources),
                )
            elif scope == "resources.health":
                catalog = await server.catalog_snapshot()
                ready = server.is_ready()
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": True,
                    "body": {"ready": ready, "hosts": catalog},
                }
                jlog(
                    logger,
                    event="mpc_resources_health",
                    ready=ready,
                    hosts=len(catalog),
                )
            elif scope and scope.startswith(
                ("prompts.", "sampling.", "resources.", "agents.", "cathedral.")
            ):
                call = payload if legacy else {"payload": payload}
                res = await server._handle_generic(call)
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": True,
                    "body": res,
                }
            else:
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": False,
                    "error": {"code": "UNKNOWN_SCOPE"},
                }

            await ws.send_text(json.dumps(frame))
    except WebSocketDisconnect:
        return
