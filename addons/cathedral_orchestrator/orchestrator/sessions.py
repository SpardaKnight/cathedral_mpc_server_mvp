from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, Dict, Any
import aiosqlite

DB_PATH = Path("/data/sessions.db")

INIT_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS sessions(
  workspace_id   TEXT NOT NULL,
  thread_id      TEXT NOT NULL,
  conversation_id TEXT,
  user_id        TEXT,
  persona_id     TEXT,
  created_ts     REAL NOT NULL,
  updated_ts     REAL NOT NULL,
  PRIMARY KEY(workspace_id, thread_id)
);
CREATE INDEX IF NOT EXISTS idx_sessions_conv ON sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_ts);
"""


async def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    for stmt in INIT_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            await db.execute(s)
    await db.commit()
    return db


async def upsert_session(workspace_id: str, thread_id: str, *, conversation_id=None, user_id=None, persona_id=None):
    now = time.time()
    async with await _connect() as db:
        await db.execute(
            """
            INSERT INTO sessions(workspace_id,thread_id,conversation_id,user_id,persona_id,created_ts,updated_ts)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(workspace_id, thread_id) DO UPDATE SET
              conversation_id=COALESCE(excluded.conversation_id, sessions.conversation_id),
              user_id=COALESCE(excluded.user_id, sessions.user_id),
              persona_id=COALESCE(excluded.persona_id, sessions.persona_id),
              updated_ts=excluded.updated_ts
            """,
            (workspace_id, thread_id, conversation_id, user_id, persona_id, now, now),
        )
        await db.commit()


async def touch_session(workspace_id: str, thread_id: str) -> None:
    async with await _connect() as db:
        await db.execute(
            "UPDATE sessions SET updated_ts=? WHERE workspace_id=? AND thread_id=?",
            (time.time(), workspace_id, thread_id),
        )
        await db.commit()


async def get_session(workspace_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
    async with await _connect() as db:
        row = await (
            await db.execute(
                "SELECT * FROM sessions WHERE workspace_id=? AND thread_id=?",
                (workspace_id, thread_id),
            )
        ).fetchone()
        return dict(row) if row else None


async def find_by_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    async with await _connect() as db:
        row = await (
            await db.execute(
                "SELECT * FROM sessions WHERE conversation_id=? ORDER BY updated_ts DESC LIMIT 1",
                (conversation_id,),
            )
        ).fetchone()
        return dict(row) if row else None
