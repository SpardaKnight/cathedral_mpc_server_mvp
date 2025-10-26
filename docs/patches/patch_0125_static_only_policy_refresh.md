# Patch 0125 — Static-only test policy refresh

## Summary
- Replace legacy Docker build guardrail with static-only CI policy in `AGENTS.md` and align documentation links.
- Normalize `pytest.ini` comments and enforce module-level skip messaging for Docker/HA-dependent tests.
- Ensure the unit test directory is tracked for discovery via `.gitkeep`.

## Testing
- Ruff, mypy, and pytest executed per static-only contract.
