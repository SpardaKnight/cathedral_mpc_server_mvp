import json
import os
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import sessions
from .logging_config import setup_logging
from .toolbridge import ToolBridge
from .vector.chroma_client import ChromaClient

router = APIRouter()

logger = setup_logging(os.environ.get("LOG_LEVEL","INFO"))

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
                    elif scope.startswith(("config.","prompts.","sampling.","resources.","agents.","cathedral.")):
                        res = await self._handle_generic(msg)
                    else:
                        res = {"ok": False, "error": "unknown_scope"}
                except Exception as e:
                    res = {"ok": False, "error": str(e)}
                frame = {"id": rid, "scope": scope, "response": res, "ts": time.time()}
                await ws.send_text(json.dumps(frame))
        except WebSocketDisconnect:
            return

    async def _handle_tools(self, msg: Dict[str,Any]) -> Dict[str,Any]:
        tool = msg.get("tool")
        payload = msg.get("payload") or {}
        return await self.tb.call(tool, payload)

    async def _handle_session(self, msg: Dict[str,Any]) -> Dict[str,Any]:
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

    async def _handle_memory(self, msg: Dict[str,Any]) -> Dict[str,Any]:
        # The orchestrator itself does not embed. Embeddings are produced by LM Studio via /v1/embeddings API.
        # This handler expects the client to pass documents/embeddings OR pass text with precomputed embedding from our HTTP path.
        action = msg.get("action")
        if action == "write":
            ids = msg.get("ids")
            embeddings = msg.get("embeddings")
            documents = msg.get("documents")
            metadatas = msg.get("metadatas")
            res = self.chroma.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            return res
        else:
            return {"ok": False, "error": "unknown_memory_action"}

    async def _handle_generic(self, msg: Dict[str,Any]) -> Dict[str,Any]:
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

@router.websocket("/mcp")
async def mcp_socket(ws: WebSocket):
    await get_server().handle(ws)
