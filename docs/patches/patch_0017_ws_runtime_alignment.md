# Patch 0017: WS runtime alignment and HA parity docs

## Summary
- Documented the canonical `/mcp` WebSocket endpoint and removed references to unused schema/tool routes.
- Clarified the application copy path `/opt/app/orchestrator` across MegaDoc and build specs.
- Added AGENTS guardrails, README reload guidance, and generic embedding examples for operator parity.
- Switched add-on build metadata to `ghcr.io/home-assistant/*-debian:bookworm` to mirror Supervisor defaults.

## Impacted Areas
- Documentation set: MegaDoc, runtime surface spec, build/base spec, README, source doclets.
- Runtime build assets: `cathedral_orchestrator/Dockerfile`, `build.json`, and dev Makefile.
- Added root `AGENTS.md` for automation guardrails.

## Validation
- Validation remains the documented docker buildx smoke test (`docs/operations/smoke-build.md`). No additional tests were run.
