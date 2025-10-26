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
9. CI is static-only. Codex may run lint with Ruff, type checks with mypy, and pure unit tests with pytest that do not require Home Assistant, Docker, networking, or device filesystems. Any HA or Supervisor run, s6 boot, Docker build, or networked check is out of scope for Codex and must not be added to CI.

10. The base image MUST be supplied by Supervisor via `BUILD_FROM` and mapped through `build.json` to `ghcr.io/home-assistant/*-base-debian:bookworm`. Do not switch tags or hardcode a base in the Dockerfile. Local smoke builds must pass `--build-arg BUILD_FROM` explicitly.

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

## Workflow Guardrails

13. Codex-initiated runs (repository_dispatch) remain authorized. GitHub-hosted automatic Actions triggered by push or pull_request are prohibited to prevent consumption of hosted runner minutes.

### CI and Test Policy (Static-Only, HA-Compliant)

**Intent.** This repository targets a Home Assistant add-on. HA add-ons are validated at runtime by the Supervisor s6 init model (PID 1 is `/init`; `init: false` required). Those invariants cannot be executed in this environment, therefore agents run only static checks and pure unit tests.

**Allowed commands - use exactly these:**
```bash
ruff check addons/cathedral_orchestrator/orchestrator clients custom_components
```
```bash
mypy addons/cathedral_orchestrator/orchestrator
```
```bash
pytest -q tests/unit
```
Note: mypy uses `ignore_missing_imports = True` from `mypy.ini`.

Forbidden - do not run:

- `docker`, `make -C dev build_amd64`, or any image build
- Supervisor, HA Core, or s6 boot assumptions
- HTTP or WebSocket calls to HA, LM Studio, or Chroma
- Reading or writing `/data` or other container paths outside a stubbed unit context

Disposition of non-compliant tests:

- `tests/test_addon_installation.py` must be skipped at module level:

  ```python
  import pytest
  pytestmark = pytest.mark.skip(reason="Disabled: requires Docker or HA runtime not available in this environment.")
  ```

  If the file contains only Docker or HA checks you may delete it instead.

Documentation anchors for agents:

- S6 v3 base image note - init: false and PID 1 enforcement: <https://developers.home-assistant.io/blog/2022/05/12/s6-overlay-base-images>
- Add-on tutorial - init: false and Supervisor lifecycle: <https://developers.home-assistant.io/docs/add-ons/tutorial>
- Add-on configuration reference - init option: <https://developers.home-assistant.io/docs/add-ons/configuration>
