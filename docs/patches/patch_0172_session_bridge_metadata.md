# Patch 0172: Cathedral session bridge for chat and embeddings

## Summary
- Introduce optional Cathedral session bridge controlled by `bridge_enabled` in options.
- Bind `/v1/chat/completions` responses to Cathedral session headers without disrupting relay behaviour.
- Propagate Cathedral session tokens into embeddings metadata for consistent workspace recall.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
