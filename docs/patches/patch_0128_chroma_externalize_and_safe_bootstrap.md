# Patch 0128: Chroma Externalization & Safe Bootstrap

## Rationale
- Remove the Python `chromadb` dependency from the add-on image to avoid musllinux wheel failures and align with the single Chroma deployment doctrine.
- Require the orchestrator to wait for healthy LM hosts and the external Chroma service before enabling auto-config and vector upserts, eliminating race conditions during Supervisor boot.
- Ensure the MPC server never applies `config.read.result` payloads until readiness gates are satisfied and expose resource health directly from the host catalog.

## Scope
- `cathedral_orchestrator/Dockerfile`
- `cathedral_orchestrator/run.sh`
- `cathedral_orchestrator/config.yaml`
- `cathedral_orchestrator/config.json`
- `cathedral_orchestrator/orchestrator/main.py`
- `cathedral_orchestrator/orchestrator/mpc_server.py`
- `cathedral_orchestrator/orchestrator/sessions.py`
- `cathedral_orchestrator/orchestrator/vector/chroma_client.py`
- `dev/venv/activate.sh`
- Documentation under `README.md`, `docs/specs/`, `docs/README_chroma_modes.md`, `docs/schemas/ADDON_OPTIONS.md`
- `cathedral_orchestrator/CHANGELOG.md`

## Acceptance
- The add-on builds without installing `chromadb` or `onnxruntime` wheels; the only vector interface is HTTP.
- `/health` returns 200 only when at least one LM host responds to `/v1/models` and the configured Chroma `/docs` endpoint is reachable; otherwise it returns 503 with diagnostic detail.
- `/api/status` reports both requested and active flags for `auto_config` and `upserts_enabled` alongside the model catalog and session counts.
- MPC memory writes create Chroma collections over HTTP, persist the collection metadata via the session manager, and skip writes when vectors are absent or the external service is unavailable.
- `run.sh` performs blocking readiness probes before launching Uvicorn in the foreground, respecting s6 v3 expectations.
- New bootstrap behaviour and version changes are documented in this patch note.
