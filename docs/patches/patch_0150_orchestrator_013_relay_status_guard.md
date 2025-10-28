# Patch 0150 – Orchestrator 0.1.3 relay and status guard

## Summary
- replace `/v1/chat/completions` handler with a raw SSE pass-through that routes by model, forwards Authorization, and guarantees the `[DONE]` sentinel when upstream terminates quietly
- harden `/api/options` updates so `chroma_mode` remains locked behind `lock_VECTOR_DB` and ignore status mirror fields during writes
- surface `auto_config_active` and `upserts_active` mirror booleans in manifests and runtime options, bumping the add-on version and changelog to 0.1.3 for Supervisor visibility

## Testing
- `ruff check cathedral_orchestrator/orchestrator`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
