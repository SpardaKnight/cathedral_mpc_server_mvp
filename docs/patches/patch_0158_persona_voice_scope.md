# Patch 0158 – Persona scaffolding, voice proxy, and MPC scope expansion

## Summary
- Seeded a persona manager that loads templates from `/data/personas`, exposes runtime state, and enables `agents.resurrect` resets.
- Added a Wyoming-compatible voice proxy and exposed `voice.*` handling so MPC clients can request synthesized speech.
- Hardened ToolBridge domain allow-listing and error handling while teaching the AnythingLLM bridge to advertise session/memory scopes and emit structured `config.read.result` frames.
- Documented the new scopes, persona workflow, and voice integration, and bumped the add-on manifest to 0.1.9.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
