# Patch 0155 – Chroma v2-first client and AnythingLLM contract alignment

## Summary
- Replace the orchestrator Chroma client with a v2-first HTTP implementation that falls back to v1 on legacy responses while preserving proactive collection creation and structured logging.
- Update the AnythingLLM Desktop MPC bridge skill to expose `runtime.handler` and declare entrypoint params so the Agent contract no longer throws when reading `params`.
- Bump the add-on manifests to 0.1.7 to trigger a Supervisor rebuild with the refreshed client and skill payloads.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
