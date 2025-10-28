# Patch 0162 – Orchestrator 0.2.3 LM Studio token metadata normalization

## Summary
- Normalize the `/v1/models` relay so LM Studio context/max token metadata is surfaced with Llama 3 70B defaults when upstream omits them.
- Ensure AnythingLLM's auto-detect sees accurate `context_window`/`max_tokens` instead of reverting to 4096.
- Bump the Home Assistant add-on manifests and changelog to version 0.2.3 for Supervisor rollout.

## Testing
- `ruff check addons/cathedral_orchestrator/orchestrator clients custom_components`
- `mypy addons/cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
