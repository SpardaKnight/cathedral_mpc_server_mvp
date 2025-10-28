# Patch 0165 – Startup non-blocking and bootstrap loop persistence

## Summary
- Convert the s6 `start.sh` LM probe to a non-blocking opportunistic check so Uvicorn always launches and logs warnings when hosts are offline.
- Keep LM discovery running after boot via the FastAPI background bootstrap loop with tightened httpx timeouts and immediate option refreshes.
- Bump Supervisor manifests and documentation to 0.2.6 with updated release notes covering the startup behavior change.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
