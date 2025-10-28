# Patch 0166 – HTTPX timeout alignment for LM catalog probes

## Summary
- Remove the global timeout from the LM AsyncClient so streaming chat relays keep their long-lived connections stable.
- Apply explicit per-request timeout tuples for LM catalog fetches and probes to cover connect, read, write, and pool phases without using open-ended values.
- Keep the Chroma client configuration unchanged while ensuring model inventory routes reuse the tuned timeout envelope.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
