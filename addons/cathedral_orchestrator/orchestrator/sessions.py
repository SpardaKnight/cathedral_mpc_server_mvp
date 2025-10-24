import sqlite3, os, threading, time, uuid
from typing import Optional, Dict, Any

DB_PATH = os.environ.get("CATHEDRAL_SESSIONS_DB", "/data/sessions.db")
INIT_SQL = "
CREATE TABLE IF NOT EXISTS sessions (
  workspace_id TEXT,
  thread_id TEXT,
  conversation_id TEXT,
  user_id TEXT,
  persona_id TEXT,
  created_ts REAL,
  updated_ts REAL,
  PRIMARY KEY (workspace_id, thread_id)
);
"

_lock = threading.Lock()

def init_db():
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(INIT_SQL)
            conn.commit()
        finally:
            conn.close()

def upsert_session(workspace_id: str, conversation_id: Optional[str], user_id: Optional[str], persona_id: Optional[str]) -> str:
    thread_id = str(uuid.uuid4())
    now = time.time()
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            # If we have an existing thread for this conversation_id, reuse
            cur = conn.execute("SELECT thread_id FROM sessions WHERE workspace_id=? AND conversation_id=?",
                               (workspace_id, conversation_id or ""))
            row = cur.fetchone()
            if row:
                thread_id = row[0]
                conn.execute("UPDATE sessions SET updated_ts=? WHERE workspace_id=? AND thread_id=?",
                             (now, workspace_id, thread_id))
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO sessions(workspace_id, thread_id, conversation_id, user_id, persona_id, created_ts, updated_ts) VALUES (?,?,?,?,?,?,?)",
                    (workspace_id, thread_id, conversation_id or "", user_id or "", persona_id or "", now, now)
                )
            conn.commit()
            return thread_id
        finally:
            conn.close()

def get_session(workspace_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            cur = conn.execute("SELECT workspace_id, thread_id, conversation_id, user_id, persona_id, created_ts, updated_ts FROM sessions WHERE workspace_id=? AND thread_id=?",
                               (workspace_id, thread_id))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "workspace_id": row[0], "thread_id": row[1], "conversation_id": row[2],
                "user_id": row[3], "persona_id": row[4], "created_ts": row[5], "updated_ts": row[6]
            }
        finally:
            conn.close()

def ttl_purge(older_than_seconds: int = 604800):
    cutoff = time.time() - older_than_seconds
    with _lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute("DELETE FROM sessions WHERE updated_ts < ?", (cutoff,))
            conn.commit()
        finally:
            conn.close()
