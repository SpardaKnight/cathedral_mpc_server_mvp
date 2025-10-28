# Patch 0169 – Models strict pass-through and context metadata endpoint

## Summary
- Restore `/v1/models` to a strict pass-through union so upstream payloads are delivered without schema mutation.
- Add `/api/models/metadata` that merges LM Studio `/api/v0/models` context metadata without touching `/v1/models` responses.
- Remove default context window/max token fallbacks from normalization to avoid misleading AnythingLLM and other clients.

## Testing
- `ruff check addons/cathedral_orchestrator/orchestrator clients custom_components`
- `mypy addons/cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
