# Patch 0119: Docker Acceptance Test Guardrail

## Summary
- purge prior acceptance tests that mocked APIs or network flows
- establish the single docker-based installation validation under `tests/`
- lock CI workflows to the add-on smoke build parity check only
- reinforce AGENTS guardrails about Docker-only testing expectations

## Testing
- pytest
- ruff
- mypy
