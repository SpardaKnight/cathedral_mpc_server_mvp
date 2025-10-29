# Patch 0170 – Orchestrator hostpool and bootstrap recovery

## Summary
- Harden LM host probing with dedicated httpx timeouts and resilience so background refreshes recover after boot.
- Execute LM host probes in parallel with bounded per-call timeouts to keep bootstrap progress from a single slow host.
- Rework the bootstrap loop to swap model catalogs only after successful responses and normalize context windows on refresh.
- Preserve cached model metadata during outages while reporting accurate readiness through the health and status endpoints.
- Align the add-on manifest files by bumping both `config.yaml` and `config.json` to version 0.2.10 for Supervisor sync.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
