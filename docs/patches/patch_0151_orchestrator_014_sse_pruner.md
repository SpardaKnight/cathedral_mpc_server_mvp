# Patch 0151 – Orchestrator 0.1.4 SSE hardening and session pruner guard

## Summary
- bump the Cathedral Orchestrator add-on to version 0.1.4
- harden the `/v1/chat/completions` SSE relay against mid-stream disconnects and enforce the `[DONE]` sentinel
- make the background session prune loop idempotent so reloads no longer trip "threads can only be started once"

## Testing
- `ruff check cathedral_orchestrator/orchestrator`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
