# Cathedral Orchestrator – Changelog

## 0.1.3 – 2025-10-25
- Fix MPC WebSocket path to resolve to `/mcp` exactly by adjusting router decorator to `/` with router prefix.
- Bind MPC WebSocket on port 5005 alongside HTTP relay on 8001.
- Version bump for Supervisor refresh.
- No behavior changes to relay, sessions, or Chroma logic.

## 0.1.1 – 2025-10-25
- Switch to Debian Bookworm base with venv at `/opt/venv`.
- Pinned runtime deps: fastapi 0.115.0, uvicorn 0.30.6, httpx 0.27.2, pydantic 2.9.2, tiktoken 0.7.0, websockets 12.0, uvloop 0.19.0, httptools 0.6.1, aiosqlite 0.20.0, chromadb 0.5.12.
- Options schema: `lm_hosts` now list(url), normalized at runtime; embedded mode guard; `upserts_enabled` switch.
- SSE streaming hardened; SQLite sessions with WAL.
