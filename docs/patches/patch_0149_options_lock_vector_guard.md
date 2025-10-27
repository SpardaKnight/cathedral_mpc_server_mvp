# Patch 0149 – Align `chroma_mode` lock with `lock_VECTOR_DB`

## Summary
- Update `/api/options` so the `chroma_mode` field respects the `lock_VECTOR_DB` flag instead of the Chroma URL lock.
- Document the guard change in the operator changelog and MegaDoc options matrix.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
