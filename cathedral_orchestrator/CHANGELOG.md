# Cathedral Orchestrator – Changelog

## [0.2.1]
- Enrich `/v1/models` with LM Studio-provided context and embedding metadata so UIs auto-detect maximum tokens instead of
  assuming 4k defaults.
- Implement a real `/api/v0/models` union with LM Studio passthrough for single-host deployments and include per-model context
  hints harvested during catalog refreshes.
- Introduce a runtime requirements manifest (including PyYAML) and install it in the Docker image alongside the pinned relay
  dependencies.

## [0.2.0]
- Add PyYAML to the add-on image and guard `import yaml` to restore FastAPI boot.
- Keep Chroma v2-first with a strict v1 fallback and redirect-friendly lookups; tolerate 404/405/409/410/422 on create/read and retry the alternate path.
- No changes to the SSE relay path; streaming remains a raw pass-through with a `[DONE]` sentinel on quiet upstream termination.

## [0.1.9]
- Wire persona templates, agents reset support, and Wyoming-compatible voice proxy into the MPC server while advertising the voice.* scope.
- Harden ToolBridge domain enforcement and error handling for Supervisor service calls.
- Extend the AnythingLLM desktop bridge handshake to cover session/memory scopes and emit structured config.read.result frames.
- Bump manifests to 0.1.9.

## [0.1.8]
- Bump manifests to 0.1.8 so Supervisor surfaces the AnythingLLM skill and Chroma client fixes.

## [0.1.7]
- Prefer Chroma API v2 with structured fallbacks to v1 while preserving proactive collection ensure and logging.
- Update the AnythingLLM MPC bridge skill to expose runtime.handler and entrypoint params for Agent compatibility.
- Bump manifests to 0.1.7.

## [0.1.6]
- Restore AnythingLLM @agent flows by implementing agents.* with a stable schema including params, and advertise capabilities in the handshake.
- Normalize resources.list to return the model catalog under both catalog and hosts.
- Fix Chroma re-embed after unload by making ensure_collection v2-first with robust v1 fallback and redirect handling.
- Replace the background prune path with a synchronous SQLite deletion inside the pruner thread to eliminate pruner thread exceptions.
- Retain the 0.1.4 SSE relay hardening and [DONE] guarantee.
- Bump manifests to 0.1.6.

## [0.1.5]
- Restore MPC `agents.*` surface and advertise capabilities in the handshake.
- Implement `agents.list` (with compatible `agents.get`/`agents.describe`) returning the Cathedral orchestrator agent.
- Normalize `resources.list` to expose the model catalog under both `catalog` and `hosts` keys for client compatibility.
- Keep `tools.*` delegated via ToolBridge and retain the SSE relay stability introduced in 0.1.4.

## [0.1.4]
- Fix streaming relay to treat httpx.StreamClosed as a clean EOF and always emit `data: [DONE]`.
- Remove idle read timeouts in the SSE path and keep a pure pass-through using `aiter_raw`.
- Maintain Authorization forwarding and `Accept: text/event-stream`.
- Keep upstream selection unified with the catalog routing used by `/v1/models`.
- Make the session prune scheduler idempotent to avoid "threads can only be started once" errors during reloads.

## [0.1.3]
- Fix `/v1/chat/completions` to stream with a true SSE pass-through using `aiter_raw`, forward Authorization, and guarantee `[DONE]` on silent upstream termination.
- Unify upstream base selection with the same routing used for model listing so the relay honors the configured LM host catalog.
- Expose `auto_config_active` and `upserts_active` in the add-on UI for operator visibility.
- Ensure `chroma_mode` respects `lock_VECTOR_DB` in `/api/options`.
- Bump add-on version so Supervisor surfaces the update reliably.

## [0.1.2]
- Align Supervisor manifests (YAML + JSON) with Home Assistant schema, including the tcp watchdog target and port descriptions.
- Refresh build metadata to use the Supervisor Debian base with standard addon labels for cross-arch visibility.
- Gate startup on LM/Chroma probes, expose readiness telemetry via `/api/status` and `/health`, and auto-create the Chroma collection when ready.
- Expand UI translations with configuration guidance and surface network labels for the relay and MPC WebSocket ports.
- Correct `/api/options` locking so `chroma_mode` obeys the `lock_VECTOR_DB` guard when auto-config pushes occur.

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
