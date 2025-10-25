# AGENTS Guide

## Scope & Identity
- This repository packages the **Cathedral Orchestrator** Home Assistant add-on.
- The add-on payload lives under `cathedral_orchestrator/` and exposes ports **8001** (HTTP) and **5005** (WebSocket `/mcp`).
- Runtime base mirrors Home Assistant: Debian Bookworm with a Python virtual environment at `/opt/venv`; application code resides at `/opt/app/orchestrator`.
- Persistent data is mounted at `/data`, including `sessions.db` and the Chroma store.

## Guardrails (Non-negotiable)
1. Never fabricate or reference fake tests. The only sanctioned validation is the Supervisor-style docker buildx smoke documented in `docs/operations/smoke-build.md`.
2. Maintain schema discipline: `lm_hosts` remains `list(url)` and manifests/docs stay in lockstep.
3. Preserve LAN-only posture. Do not introduce in-container TLS termination or WAN exposure.
4. Uphold the single-writer rule for `/data`; avoid multi-writer patterns or background daemons that mutate shared state.
5. Do not "clean up" imports or dependencies required by contract (e.g., `HTTPException`, `StreamingResponse`, `PlainTextResponse`, `websockets`, `uvloop`, `httptools`).
6. Do not switch away from Debian+`/opt/venv` or fall back to system `pip`/Alpine bases.
7. Keep ports and filesystem paths stable: `/opt/app/orchestrator`, `/opt/venv`, `/data` mounts.
8. Treat docs as first-class: any behavioral or manifest change must update the MegaDoc, schema docs, and CHANGELOG in the same PR.
9. The only authorized test is the Docker build acceptance test that validates add-on installation and visibility inside Home Assistant. No other test suites, mock servers, or network simulations are permitted. Codex must not run or recreate any non-Docker test.

## Task Classes & Acceptance
- Documentation-only updates must honor the guardrails and keep schema references accurate.
- Manifest/schema adjustments require matching updates across YAML, JSON, and docs.
- Docker/runtime changes mandate version bumps and documentation updates.
- Application surface changes (HTTP/WS endpoints) require coordinated updates to specs and operator guidance.
- Coordination with AnythingLLM or external clients must avoid introducing forbidden modules or schema drift.

## PR & Version Discipline
- Bump the add-on `version` whenever Dockerfile or manifest changes land.
- Record source-impacting changes in `docs/patches/` with clear rationale.
- Never commit secrets or tokens; logs must remain safe for sharing.

## Operator Quick Checks
- `curl -s http://homeassistant.local:8001/health | jq`
- `curl -s http://homeassistant.local:8001/v1/models | jq`
- `curl -s http://homeassistant.local:8001/v1/embeddings -H 'Content-Type: application/json' -d '{"input":"ping","model":"<your-embed-model-id>"}'`
- After repository updates, use **⋮ → Reload** in the Add-on Store if the add-on is not visible.


13. Codex-initiated runs (repository_dispatch) remain authorized. GitHub-hosted automatic Actions triggered by push or pull_request are prohibited to prevent consumption of hosted runner minutes.
