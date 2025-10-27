# Cathedral Orchestrator – Changelog

## [0.1.2]
- Align Supervisor manifest defaults with Cathedral Orchestrator v3.1, including `/api/status` telemetry and Chroma provisioning.
- Expose UI translations and port descriptions for the relay and MPC WebSocket endpoints.
- Add watchdog health probes and readiness gating to satisfy Supervisor validation.
- Harden the Debian base with Supervisor build metadata labels for cross-arch builds.

## [1.1.16]
- Restore `/v1/chat/completions` to relay through the configured LM host catalog instead of a hardcoded LAN endpoint while retaining raw SSE streaming.
- Log upstream transport failures as structured 502 errors and keep Authorization forwarding minimal for pass-through compliance.
- Update manifests and documentation to describe the hostpool-driven relay.

## [1.1.15]
- Fix `/v1/chat/completions` relay to enter the upstream `httpx.AsyncClient.stream` context properly for uninterrupted SSE proxying.
- Bump Supervisor manifest metadata to release the streaming stability fix.

## [1.1.14]
- Point `/v1/chat/completions` directly at the dedicated LM Studio relay on `http://192.168.1.175:1234` using a raw streaming proxy.
- Document the fixed upstream routing and bump Supervisor manifest version to release the relay update.

## [1.1.13]
- Fix streaming relay to treat `httpx.StreamClosed` as a clean EOF and always emit the SSE `data: [DONE]` trailer.
- Add `/api/v0/models` alias for legacy clients probing the deprecated path.

## [1.1.12]
- Implement heartbeat-first Chroma readiness with v2→v1→docs fallback and redirect following.
- Make the session TTL prune scheduler idempotent so reloads spawn fresh threads without crashes.

## [1.1.11]
- Add Supervisor Sync + s6 v3 hard rules to AGENTS.md and enforce them with static pytest guards.

## [1.1.10]
- Bump Supervisor manifest metadata to restore update detection and sync JSON mirror.

## [1.1.9]
- Fix Uvicorn import path by switching to `--app-dir /opt/app` and exporting `PYTHONPATH` before launch.

## [1.1.8]
- Manifest discipline: `init: false` affirmed, supervisor startup retained, and version bumped for release sync.
- Dockerfile aligned with HA base entrypoint expectations (no CMD/ENTRYPOINT overrides; relies on `/init`).
- Service layout hardened: execlineb `run` delegating to `/opt/app/start.sh` with LM/Chroma probes before `exec uvicorn`.
- s6 finish handler, executable bits, and LF normalization tracked in git to prevent drift.

## [1.1.6]
- Refactored add-on startup: removed run.sh, resolved s6-overlay PID 1 conflict, moved all launch logic to service script.

## 1.1.5 – 2025-10-27
- Externalized vector persistence to an HTTP Chroma service and removed chromadb from the add-on image.
- Added safe bootstrap gating that requires healthy LM hosts and Chroma before enabling auto-config or vector upserts.
- Simplified runtime install docs and tooling to reflect HTTP-only Chroma usage.

## 1.1.4 – 2025-10-26
- Run the add-on under s6 v3 with `/init` as PID 1, moving startup into `/etc/services.d` and declaring `init: false`. No functional changes.

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
