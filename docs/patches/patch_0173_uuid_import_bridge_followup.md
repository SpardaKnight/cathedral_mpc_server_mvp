# Patch 0173 — UUID import for session bridge

## Summary
- add explicit `uuid` import in `orchestrator/main.py` so session bridge helpers can mint tokens

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit
