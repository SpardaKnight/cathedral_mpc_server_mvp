# Patch 0119 — Cathedral Orchestrator status/options v3.1

## Summary
- Align `/api/status` payload with Cathedral v3.1 (session counts, host catalog, option flags).
- Harden `/api/options` read/write path to persist Supervisor locks and trigger live client reloads.
- Add `reload_clients_from_options` workflow to rebuild the LM host pool and Chroma client on-demand.

## Implementation Notes
- Introduced a `HostPool` helper to manage LM Studio discovery and caches refreshed via the shared httpx client.
- Added `SessionManager.list_active()` integration for accurate session counts sourced from the existing SQLite store.
- Writes to `/data/options.json` now use atomic temp-file replacement and log telemetry for observability and failure tracing.
- Options schema now exposes auto-config and per-endpoint lock toggles so Supervisor UIs persist changes across restarts.

## Files
- `addons/cathedral_orchestrator/orchestrator/main.py`
- `addons/cathedral_orchestrator/config.yaml`
- `addons/cathedral_orchestrator/config.json`
- `addons/cathedral_orchestrator/CHANGELOG.md`

## Testing
- pytest
- ruff
- mypy
