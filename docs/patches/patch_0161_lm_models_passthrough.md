# Patch 0161 – LM models passthrough and host normalization

## Summary
- Normalize configured LM host URLs by trimming trailing `/v1` components and slashes to prevent misrouting.
- Preserve upstream `/v1/models` payloads (including LM Studio metadata) and expose a HEAD probe for provider readiness checks.
- Update manifests, changelog, and UI strings to document the compatibility fix and publish as 0.2.2 (superseding 0.2.1).

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
