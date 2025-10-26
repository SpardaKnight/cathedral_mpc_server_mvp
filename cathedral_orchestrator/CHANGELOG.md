# Cathedral Orchestrator – Changelog

## 1.1.3 – 2025-10-26
- Ensure session update helpers use workspace-aware keys for mutation safety.
- No surface API or configuration changes.

## 1.1.2 – 2025-10-26
- Extend session schema to v3.1 with host, health, and Chroma linkage columns and migrate existing databases.
- Add a background scheduler that prunes idle sessions after 120 minutes without disrupting WAL mode.
- No surface API changes; status and Supervisor manifests remain compatible.

## 1.1.1 – 2025-10-26
- Adjust `/api/status` to expose host catalogs as lists of model identifiers per v3.1.
- Harden `/health` readiness gating to require an LM client and configured hosts before reporting OK.
- Default `auto_config` to `true` and sync manifests/schema/docs.

## 1.1.0 – 2025-10-26
- Implemented v3.1 `/api/status` payload with session counts, host catalog, and option flags.
- Added Supervisor option reload pipeline with HostPool/Chroma rebuild and persisted lock toggles.
- Bumped defaults and manifests for new auto-config and lock fields.


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
