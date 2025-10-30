# Patch 0174: MPC tools cache time import fix

## Summary
- ensure the MPC server imports `time` so the tools cache TTL logic can execute without runtime errors.

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit
