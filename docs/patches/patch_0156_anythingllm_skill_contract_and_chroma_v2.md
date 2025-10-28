# Patch 0156 – AnythingLLM skill contract alignment and Chroma v2-first upserts

## Summary
- Replace the AnythingLLM Desktop agent skill manifest and handler to satisfy the skill-1.0.0 contract, persist credentials in a local `.env`, and autostart the Cathedral MPC bridge when configured.
- Teach the orchestrator Chroma client to prefer the `/api/v2/collections/{id}/add` endpoint with structured fallbacks, improving resilience against servers that reject legacy v1 routes.
- Confirm manifest version 0.1.7 remains current for the add-on release containing these fixes.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
