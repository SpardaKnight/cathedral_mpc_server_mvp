# Patch 0129 — PID crash trace logging hardening

## Summary
- harden `run.sh` preflight probes to emit explicit `[ERROR]` messages when LM hosts or Chroma are unreachable
- keep the add-on blocked until dependent services respond, avoiding silent PID-1 crashes without context

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit
