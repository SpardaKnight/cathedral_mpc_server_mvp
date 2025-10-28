# Patch 0168 – HTTPX timeout follow-up

## Summary
- Reinstate an explicit `Timeout(None)` on the LM AsyncClient so streaming relays never inherit a five-second default deadline.
- Keep per-request timeout guards for LM catalog aggregation, passthrough, and probe calls aligned with four-field settings.
- Bump the Cathedral Orchestrator add-on manifests and changelog to version 0.2.8 for Supervisor visibility of the hotfix.

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit
