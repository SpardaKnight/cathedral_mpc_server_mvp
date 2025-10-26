import json
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import sessions
from .logging_config import setup_logging
from .toolbridge import ToolBridge
from .vector.chroma_client import ChromaClient

router = APIRouter()

logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))


class MPCServer:
    def __init__(self, toolbridge: ToolBridge, chroma: ChromaClient):
        self.tb = toolbridge
        self.chroma = chroma

    async def handle(self, ws: WebSocket):
        await ws.accept()
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                scope = msg.get("scope")  # e.g., 'session.create', 'tools.call'
                rid = msg.get("id") or str(uuid.uuid4())
                try:
                    if scope.startswith("tools."):
                        res = await self._handle_tools(msg)
                    elif scope.startswith("session."):
                        res = await self._handle_session(msg)
                    elif scope.startswith("memory."):
                        res = await self._handle_memory(msg)
                    elif scope.startswith(
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
                except Exception as e:
                    res = {"ok": False, "error": str(e)}
                frame = {"id": rid, "scope": scope, "response": res, "ts": time.time()}
                await ws.send_text(json.dumps(frame))
        except WebSocketDisconnect:
            return

    async def _handle_tools(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        tool = msg.get("tool")
        if not isinstance(tool, str) or not tool:
            return {"ok": False, "error": "invalid_tool_name"}
        payload = msg.get("payload") or {}
        return await self.tb.call(tool, payload)

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
            return {"ok": True, "thread_id": thread_id, "session": session}
        elif action == "resume":
            thread_id = msg.get("thread_id")
            if not thread_id:
                return {"ok": False, "error": "thread_id_required"}
            row = await sessions.get_session(workspace_id, thread_id)
            if row:
                await sessions.touch_session(workspace_id, thread_id)
            return {"ok": bool(row), "session": row}
        else:
            return {"ok": False, "error": "unknown_session_action"}

    async def _handle_memory(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        # The orchestrator itself does not embed. Embeddings are produced by LM Studio via /v1/embeddings API.
        # This handler expects the client to pass documents/embeddings OR pass text with precomputed embedding from our HTTP path.
        action = msg.get("action")
        if action == "write":
            ids = msg.get("ids")
            embeddings = msg.get("embeddings")
            documents = msg.get("documents")
            metadatas = msg.get("metadatas")
            res = self.chroma.upsert(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )
            return res
        else:
            return {"ok": False, "error": "unknown_memory_action"}

    async def _handle_generic(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        # Minimal echo for spec completeness; can be extended in Phase-2+
        return {"ok": True, "echo": msg.get("payload", {})}


mpc_server_singleton: Optional[MPCServer] = None


def get_server() -> MPCServer:
    global mpc_server_singleton
    if mpc_server_singleton is None:
        raise RuntimeError("MPC server not initialized")
    return mpc_server_singleton


def set_server(server: MPCServer):
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
                    except Exception as e:
                        frame = {
                            "id": rid,
                            "type": "mcp.response",
                            "ok": False,
                            "error": {"code": "APPLY_FAIL", "message": str(e)},
                        }
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
