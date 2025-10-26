from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite

from .logging_config import jlog

DB_PATH = Path("/data/sessions.db")

INIT_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous = NORMAL;
CREATE TABLE IF NOT EXISTS sessions(
  workspace_id            TEXT NOT NULL,
  thread_id               TEXT NOT NULL,
  conversation_id         TEXT,
  user_id                 TEXT,
  persona_id              TEXT,
  host_url                TEXT,
  model_id                TEXT,
  health_state            TEXT DEFAULT 'ok',
  chroma_collection_id    TEXT,
  chroma_collection_name  TEXT,
  created_ts              REAL NOT NULL,
  updated_ts              REAL NOT NULL,
  PRIMARY KEY(workspace_id, thread_id)
);
CREATE INDEX IF NOT EXISTS idx_sessions_conv ON sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_ts);
"""


logger = logging.getLogger("cathedral")


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    try:
        cursor = await db.execute("PRAGMA table_info(sessions)")
        rows = await cursor.fetchall()
        columns = {row[1] for row in rows}
    except Exception as exc:  # pragma: no cover - sqlite guard
        jlog(
            logger,
            level="ERROR",
            event="session_schema_probe_failed",
            error=str(exc),
        )
        return

    migrations = []

    def plan(column: str, sql: str) -> None:
        if column not in columns:
            migrations.append((column, sql))

    plan("host_url", "ALTER TABLE sessions ADD COLUMN host_url TEXT")
    plan("model_id", "ALTER TABLE sessions ADD COLUMN model_id TEXT")
    plan(
        "health_state",
        "ALTER TABLE sessions ADD COLUMN health_state TEXT DEFAULT 'ok'",
    )
    plan(
        "chroma_collection_id",
        "ALTER TABLE sessions ADD COLUMN chroma_collection_id TEXT",
    )
    plan(
        "chroma_collection_name",
        "ALTER TABLE sessions ADD COLUMN chroma_collection_name TEXT",
    )

    if not migrations:
        return

    for column, sql in migrations:
        try:
            await db.execute(sql)
            jlog(logger, event="session_schema_migrated", column=column)
        except Exception as exc:  # pragma: no cover - sqlite guard
            jlog(
                logger,
                level="ERROR",
                event="session_schema_migration_failed",
                column=column,
                error=str(exc),
            )
    await db.commit()


async def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    for stmt in INIT_SQL.strip().split(";"):
        s = stmt.strip()
        if s:
            await db.execute(s)
    await db.commit()
    await _ensure_schema(db)
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


async def set_host(
    workspace_id: str,
    thread_id: str,
    host_url: Optional[str],
    model_id: Optional[str],
) -> None:
    now = time.time()
    try:
        async with await _connect() as db:
            cursor = await db.execute(
                """
                UPDATE sessions
                SET host_url=?, model_id=?, updated_ts=?
                WHERE workspace_id=? AND thread_id=?
                """,
                (host_url, model_id, now, workspace_id, thread_id),
            )
            await db.commit()
            jlog(
                logger,
                event="session_set_host",
                workspace_id=workspace_id,
                thread_id=thread_id,
                host=host_url,
                model=model_id,
                updated=cursor.rowcount,
            )
    except Exception as exc:  # pragma: no cover - sqlite guard
        jlog(
            logger,
            level="ERROR",
            event="session_set_host_failed",
            workspace_id=workspace_id,
            thread_id=thread_id,
            error=str(exc),
        )


async def set_health(
    workspace_id: str, thread_id: str, health_state: str
) -> None:
    now = time.time()
    try:
        async with await _connect() as db:
            cursor = await db.execute(
                """
                UPDATE sessions
                SET health_state=?, updated_ts=?
                WHERE workspace_id=? AND thread_id=?
                """,
                (health_state, now, workspace_id, thread_id),
            )
            await db.commit()
            jlog(
                logger,
                event="session_set_health",
                workspace_id=workspace_id,
                thread_id=thread_id,
                health=health_state,
                updated=cursor.rowcount,
            )
    except Exception as exc:  # pragma: no cover - sqlite guard
        jlog(
            logger,
            level="ERROR",
            event="session_set_health_failed",
            workspace_id=workspace_id,
            thread_id=thread_id,
            error=str(exc),
        )


async def set_collection(
    workspace_id: str, thread_id: str, name: str, id: str
) -> None:
    now = time.time()
    try:
        async with await _connect() as db:
            cursor = await db.execute(
                """
                UPDATE sessions
                SET chroma_collection_name=?, chroma_collection_id=?, updated_ts=?
                WHERE workspace_id=? AND thread_id=?
                """,
                (name, id, now, workspace_id, thread_id),
            )
            await db.commit()
            jlog(
                logger,
                event="session_set_collection",
                workspace_id=workspace_id,
                thread_id=thread_id,
                collection=name,
                collection_id=id,
                updated=cursor.rowcount,
            )
    except Exception as exc:  # pragma: no cover - sqlite guard
        jlog(
            logger,
            level="ERROR",
            event="session_set_collection_failed",
            workspace_id=workspace_id,
            thread_id=thread_id,
            error=str(exc),
        )


async def list_active() -> int:
    try:
        async with await _connect() as db:
            row = await (await db.execute("SELECT COUNT(*) FROM sessions")).fetchone()
            count = int(row[0]) if row else 0
            jlog(logger, event="session_count", count=count)
            return count
    except Exception as exc:  # pragma: no cover - sqlite guard
        jlog(logger, level="ERROR", event="session_count_failed", error=str(exc))
        return 0


async def prune_idle(ttl_minutes: int = 120) -> int:
    cutoff = time.time() - (ttl_minutes * 60)
    try:
        async with await _connect() as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE updated_ts < ?",
                (cutoff,),
            )
            await db.commit()
            count = cursor.rowcount if cursor.rowcount is not None else 0
            jlog(
                logger,
                event="session_pruned_idle",
                ttl_minutes=ttl_minutes,
                pruned=count,
            )
            return int(count)
    except Exception as exc:  # pragma: no cover - sqlite guard
        jlog(
            logger,
            level="ERROR",
            event="session_prune_failed",
            ttl_minutes=ttl_minutes,
            error=str(exc),
        )
        return 0
