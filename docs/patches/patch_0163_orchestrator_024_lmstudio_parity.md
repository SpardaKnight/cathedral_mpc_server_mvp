# Patch 0163 – Orchestrator 0.2.4 LM Studio parity and packaging

## Summary
- Preserve upstream `/v1/models` payloads, cache raw objects, and expose them directly so AnythingLLM recovers auto-detected token limits.
- Normalize configured LM Studio host URLs (strip `/v1` and redundant slashes) during option reloads and API updates to stop doubled `/v1` paths.
- Ensure Docker builds install the add-on requirements (including `PyYAML>=6.0.2`) and bump manifests/changelog to version 0.2.4.

## Testing
- `ruff check addons/cathedral_orchestrator/orchestrator clients custom_components`
- `mypy addons/cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
