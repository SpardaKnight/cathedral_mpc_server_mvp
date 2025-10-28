# Patch 0164 – Orchestrator bootstrap hardening and LM probe guard

## Summary
- Replace blocking LM bootstrap in `lifespan` with a resilient background loop so the API comes up even when providers are offline.
- Tighten LM httpx client timeouts and harden host pool/catalog refresh logic to avoid propagating probe failures during startup.
- Ensure option edits immediately refresh clients and bootstrap state so administrators can recover from bad host entries without restarts.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
