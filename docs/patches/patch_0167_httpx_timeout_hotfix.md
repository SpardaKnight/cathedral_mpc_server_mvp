# Patch 0167 – HTTPX Timeout Hotfix

## Summary
- Remove the global timeout from the LM AsyncClient so SSE relays keep streaming without premature disconnects.
- Apply four-field per-request HTTPX timeouts for LM catalog refreshes and probe calls to bound connect/read/write/pool phases.
- Bump Supervisor manifests and changelog to version 0.2.7 so Home Assistant surfaces the update.

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit
