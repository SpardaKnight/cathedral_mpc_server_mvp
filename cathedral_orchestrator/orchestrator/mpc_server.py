from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import persona_manager, sessions, voice_proxy
from .logging_config import jlog, setup_logging
from .toolbridge import ToolBridge
from .vector.chroma_client import ChromaClient

router = APIRouter()

logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

HANDLED_SCOPES = (
    "session.*",
    "memory.*",
    "prompts.*",
    "config.*",
    "sampling.*",
    "resources.*",
    "agents.*",
    "voice.*",
    "cathedral.*",
)

DELEGATED_SCOPES = ("tools.*",)


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
        # Small TTL cache for tools list to avoid hammering HA
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._tools_cache_ts: float = 0.0
        self._tools_ttl: float = 300.0

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

    async def _tools_list_cached(self) -> List[Dict[str, Any]]:
        now = time.time()
        if self._tools_cache is not None and (now - self._tools_cache_ts) < self._tools_ttl:
            jlog(logger, event="mpc_tools_cache_hit", count=len(self._tools_cache))
            return self._tools_cache
        tools = await self.tb.list_services()
        self._tools_cache = tools
        self._tools_cache_ts = now
        jlog(logger, event="mpc_tools_cache_refresh", count=len(tools))
        return tools

    async def _assign_session_host(
        self, workspace_id: str, thread_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        from . import main as orchestrator_main

        hosts_map = orchestrator_main.LM_HOSTS
        host_values = [value.rstrip("/") for value in hosts_map.values()]
        if not host_values:
            jlog(
                logger,
                level="WARN",
                event="mpc_session_no_hosts",
                workspace_id=workspace_id,
                thread_id=thread_id,
            )
            return None, None
        healthy = [
            host
            for host in host_values
            if orchestrator_main.HOST_HEALTH.get(host) == "ok"
        ]
        host_choice = healthy[0] if healthy else host_values[0]
        catalog_models = orchestrator_main.MODEL_CATALOG.get(host_choice) or []
        model_id = catalog_models[0] if catalog_models else None
        await sessions.set_host(workspace_id, thread_id, host_choice, model_id)
        jlog(
            logger,
            event="mpc_session_host_assigned",
            workspace_id=workspace_id,
            thread_id=thread_id,
            host=host_choice,
            model=model_id,
        )
        return host_choice, model_id

    async def _ensure_session_collection(
        self, workspace_id: str, thread_id: str
    ) -> Optional[str]:
        if self.chroma is None:
            return None
        collection_name = self._collection_name_provider()
        if not collection_name:
            return None
        collection_id = await self.chroma.ensure_collection(collection_name)
        if collection_id:
            await sessions.set_collection(
                workspace_id, thread_id, collection_name, collection_id
            )
            jlog(
                logger,
                event="mpc_session_collection_ready",
                workspace_id=workspace_id,
                thread_id=thread_id,
                collection=collection_name,
                collection_id=collection_id,
            )
        return collection_id

    async def _handle_agents(
        self, scope: str, workspace_id: Optional[str]
    ) -> Dict[str, Any]:
        """Return Cathedral agent metadata for MCP agent discovery."""
        agent_record = {
            "id": "cathedral",
            "name": "Cathedral",
            "kind": "orchestrator",
            "capabilities": {
                "handled": list(HANDLED_SCOPES),
                "delegated": list(DELEGATED_SCOPES),
            },
            "params": {
                "chat": {"model": "auto", "temperature": 0.7, "top_p": 0.9},
                "embedding": {"model": "auto"},
            },
            "metadata": {
                "workspace_id": workspace_id or "default",
                "version": "0.1.9",
            },
        }

        if scope == "agents.list":
            personas = sorted(persona_manager.list_personas().keys())
            tools = await self._tools_list_cached()
            payload: Dict[str, Any] = {
                "agents": [agent_record],
                "personas": personas,
                "tools": tools,
            }
        elif scope in {"agents.get", "agents.describe"}:
            payload = {"agent": agent_record}
        elif scope == "agents.resurrect":
            payload = {}
        else:
            payload = {}

        jlog(
            logger,
            event="mpc_agents_response",
            scope=scope,
            workspace_id=workspace_id or "default",
            keys=list(payload.keys()),
        )
        return payload

    async def _handle_voice(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        text = (
            msg.get("text")
            or msg.get("content")
            or (msg.get("body") or {}).get("text")
            or (msg.get("payload") or {}).get("text")
        )
        if not text:
            jlog(logger, level="ERROR", event="mpc_voice_missing_text")
            return {"ok": False, "error": "text_required"}
        audio = await voice_proxy.synthesize(str(text))
        if not audio:
            jlog(logger, level="ERROR", event="mpc_voice_synthesis_failed")
            return {"ok": False, "error": "synthesis_failed"}
        import base64

        encoded = base64.b64encode(audio).decode("ascii")
        jlog(logger, event="mpc_voice_synthesized", bytes=len(audio))
        return {
            "ok": True,
            "audio": {"format": "pcm", "data": encoded},
        }

    async def _handle_resources(self) -> Dict[str, Any]:
        """Expose the model catalog under both catalog and hosts for client compatibility."""

        catalog = await self.catalog_snapshot()
        normalized = {"catalog": dict(catalog), "hosts": dict(catalog)}
        jlog(logger, event="mpc_resources_list", hosts=len(catalog))
        return normalized

    async def handle(self, ws: WebSocket):
        await ws.accept()
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                scope = msg.get("scope")
                rid = msg.get("id") or str(uuid.uuid4())
                try:
                    if scope == "tools.list":
                        res = {"ok": True, "tools": await self._tools_list_cached()}
                    elif scope and scope.startswith("tools."):
                        res = await self._handle_tools(msg)
                    elif scope and scope.startswith("session."):
                        res = await self._handle_session(msg)
                    elif scope and scope.startswith("memory."):
                        res = await self._handle_memory(msg)
                    elif scope == "resources.list":
                        res = {"ok": True, "body": await self._handle_resources()}
                    elif scope == "resources.health":
                        from . import main as orchestrator_main

                        host_health = dict(orchestrator_main.HOST_HEALTH)
                        body = {
                            "ready": self.is_ready(),
                            "host_health": host_health,
                            "ts": datetime.utcnow().isoformat() + "Z",
                        }
                        jlog(
                            logger,
                            event="mpc_resources_health",
                            ready=body["ready"],
                            hosts=len(host_health),
                        )
                        res = {"ok": True, "body": body}
                    elif scope and scope.startswith("agents."):
                        workspace_id = msg.get("workspace_id")
                        if scope == "agents.resurrect":
                            persona_id = (
                                msg.get("persona_id")
                                or (msg.get("body") or {}).get("persona_id")
                            )
                            ok = bool(persona_id) and persona_manager.reset(
                                str(persona_id)
                            )
                            res = {
                                "ok": ok,
                                "body": {
                                    "persona_id": persona_id,
                                    "reset": ok,
                                },
                            }
                        else:
                            res = {
                                "ok": True,
                                "body": await self._handle_agents(scope, workspace_id),
                            }
                    elif scope and scope.startswith("voice."):
                        res = await self._handle_voice(msg)
                    elif scope and scope.startswith(
                        (
                            "config.",
                            "prompts.",
                            "sampling.",
                            "resources.",
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
            persona_id = msg.get("persona_id") or "default"
            persona_payload = persona_manager.get(persona_id)
            if persona_payload is None:
                jlog(
                    logger,
                    level="WARN",
                    event="mpc_session_persona_missing",
                    requested=persona_id,
                )
                persona_id = "default"
                persona_payload = persona_manager.get("default")
            thread_id = msg.get("thread_id") or f"thr_{int(time.time()*1000):x}"
            await sessions.upsert_session(
                workspace_id,
                thread_id,
                conversation_id=conversation_id,
                user_id=user_id,
                persona_id=persona_id,
            )
            await self._assign_session_host(workspace_id, thread_id)
            await self._ensure_session_collection(workspace_id, thread_id)
            session = await sessions.get_session(workspace_id, thread_id)
            jlog(
                logger,
                event="mpc_session_created",
                workspace_id=workspace_id,
                thread_id=thread_id,
                persona_id=persona_id,
            )
            return {
                "ok": True,
                "thread_id": thread_id,
                "session": session,
                "persona": persona_payload or {},
            }
        if action == "resume":
            thread_id = msg.get("thread_id")
            if not thread_id:
                jlog(logger, level="ERROR", event="mpc_session_resume_missing")
                return {"ok": False, "error": "thread_id_required"}
            session_row = await sessions.get_session(workspace_id, thread_id)
            if session_row is not None:
                await sessions.touch_session(workspace_id, thread_id)
                if not session_row.get("host_url"):
                    await self._assign_session_host(workspace_id, thread_id)
                    session_row = await sessions.get_session(workspace_id, thread_id)
                if session_row is not None and not session_row.get(
                    "chroma_collection_id"
                ):
                    await self._ensure_session_collection(workspace_id, thread_id)
                    session_row = await sessions.get_session(workspace_id, thread_id)
            jlog(
                logger,
                event="mpc_session_resumed",
                workspace_id=workspace_id,
                thread_id=thread_id,
                found=bool(session_row),
            )
            return {"ok": bool(session_row), "session": session_row}
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
                    "server": "cathedral-mpc/1.2",
                    "scopes": {
                        "handled": list(HANDLED_SCOPES),
                        "delegated": list(DELEGATED_SCOPES),
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
                from . import main as orchestrator_main

                current_options = dict(orchestrator_main.CURRENT_OPTIONS)
                auto_allowed = (
                    server.is_ready()
                    and server.auto_config_allowed()
                    and current_options.get("auto_config", True)
                )
                if not auto_allowed:
                    frame = {
                        "id": rid,
                        "type": "mcp.response",
                        "ok": False,
                        "error": {"code": "BOOTSTRAP_PENDING"},
                    }
                else:
                    envmap = body if not legacy else msg.get("payload") or {}
                    patch: Dict[str, Any] = {}
                    if isinstance(envmap, dict):
                        chroma_url = envmap.get("CHROMA_URL")
                        lmstudio_path = envmap.get("LMSTUDIO_BASE_PATH")
                        if (
                            chroma_url
                            and not current_options.get("lock_CHROMA_URL", False)
                        ):
                            patch["chroma_mode"] = "http"
                            patch["chroma_url"] = chroma_url
                        if (
                            lmstudio_path
                            and not current_options.get("lock_hosts", False)
                            and not current_options.get(
                                "lock_LMSTUDIO_BASE_PATH", False
                            )
                        ):
                            patch["lm_hosts"] = [lmstudio_path]
                    if patch:
                        try:
                            async with httpx.AsyncClient(timeout=10.0) as client:
                                response = await client.post(
                                    "http://127.0.0.1:8001/api/options", json=patch
                                )
                                ok = response.status_code == 200
                        except Exception as exc:  # pragma: no cover - network guard
                            ok = False
                            jlog(
                                logger,
                                level="ERROR",
                                event="mpc_config_apply_failed",
                                error=str(exc),
                            )
                            frame = {
                                "id": rid,
                                "type": "mcp.response",
                                "ok": False,
                                "error": {"code": "APPLY_FAIL", "message": str(exc)},
                            }
                        else:
                            frame = {
                                "id": rid,
                                "type": "mcp.response",
                                "ok": ok,
                                "body": {"applied": patch if ok else {}},
                            }
                            jlog(
                                logger,
                                event="mpc_config_applied",
                                ok=ok,
                                keys=list(patch.keys()),
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
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": True,
                    "body": await server._handle_resources(),
                }
            elif scope == "resources.health":
                from . import main as orchestrator_main

                health = dict(orchestrator_main.HOST_HEALTH)
                ready = server.is_ready()
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": True,
                    "body": {
                        "ready": ready,
                        "host_health": health,
                        "ts": datetime.utcnow().isoformat() + "Z",
                    },
                }
                jlog(
                    logger,
                    event="mpc_resources_health",
                    ready=ready,
                    hosts=len(health),
                )
            elif scope and scope.startswith("agents."):
                workspace_id = (
                    headers.get("workspace_id")
                    or body.get("workspace_id")
                    or payload.get("workspace_id")
                )
                if scope == "agents.resurrect":
                    persona_id = (
                        body.get("persona_id")
                        or payload.get("persona_id")
                        or headers.get("persona_id")
                    )
                    ok = bool(persona_id) and persona_manager.reset(str(persona_id))
                    frame = {
                        "id": rid,
                        "type": "mcp.response",
                        "ok": ok,
                        "body": {
                            "persona_id": persona_id,
                            "reset": ok,
                        },
                    }
                else:
                    frame = {
                        "id": rid,
                        "type": "mcp.response",
                        "ok": True,
                        "body": await server._handle_agents(scope, workspace_id),
                    }
            elif scope and scope.startswith("voice."):
                voice_payload = payload if legacy else body
                res = await server._handle_voice(voice_payload)
                frame = {
                    "id": rid,
                    "type": "mcp.response",
                    "ok": bool(res.get("ok")),
                    "body": res,
                }
            elif scope and scope.startswith(
                ("prompts.", "sampling.", "resources.", "cathedral.")
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
