# Patch 0134 – Uvicorn app-dir import path correction

## Summary
- ensure `/opt/app/start.sh` switches to `/opt/app` and exports `PYTHONPATH` before invoking Uvicorn
- launch Uvicorn with `--app-dir /opt/app orchestrator.main:app` so the orchestrator package resolves correctly
- bump add-on version to 1.1.9 and document the runtime adjustment

## Testing
- ruff check addons/cathedral_orchestrator/orchestrator clients custom_components
- mypy addons/cathedral_orchestrator/orchestrator
- pytest -q tests/unit
