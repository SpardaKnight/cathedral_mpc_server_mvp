# RUNBOOK — Cathedral MPC Server MVP

Updated: 2025-10-24T23:07:38.826014Z

## Prerequisites

- Home Assistant OS/Supervised with Supervisor & Add-on Store.
- Windows 11 host with:
  - **LM Studio** REST server (OpenAI-compatible endpoints), e.g. `http://192.168.1.71:1234/v1`.
  - **Chroma** server in HTTP mode, e.g. `http://192.168.1.71:8000` (`/docs` should load).
- LAN connectivity between HA and Windows host.

## Install — Add-on

1. Copy `addons/cathedral_orchestrator/` into your local add-on repository folder.
2. In HA UI → Settings → Add-ons → Add-on Store → “⋮” → Repositories → Add local path.
3. Open the **Cathedral Orchestrator** add-on → Configure options:
   - `lm_hosts`: map host name → base URL (e.g., `{"default": "http://192.168.1.71:1234"}`).
   - `chroma_url`: e.g., `http://192.168.1.71:8000`.
   - Choose `log_level`, toggles, etc.
4. Start the add-on. The add-on preflights LM Studio `/v1/models` and Chroma `/docs` before serving.

## Install — Integrations

Copy `custom_components/` folders into HA `config/custom_components/` and restart HA.

### Cathedral MPC (UI)

- Add integration → **Cathedral MPC**.
- Set Orchestrator URL (default `http://homeassistant.local:8001`).
- Use Options to change models, temperature, toggles. Options hot-apply by calling add-on `/api/options`, and also persist by updating add-on options via Supervisor API.

### Cathedral Agent (Assist)

- Add integration → **Cathedral Agent**.
- Go to **Settings → Voice Assistants**; create/select an Assistant and pick **Cathedral Agent** as the conversation agent.
- Test voice or text; the agent POSTs to Orchestrator `/v1/chat/completions` with a stable `thread_id` derived from `conversation_id`.

## Acceptance Tests

See `scripts/acceptance/` for cURL and Python scripts that exercise:
- `/v1/models` merge & health
- Chat SSE relay (ends with `data: [DONE]`)
- `/v1/embeddings` → Chroma upsert (visible via logs)
- MPC WebSocket handshake + sessions + config.read/write + tools.call (allowed domains)
- Assist round-trip
- Options hot-apply & persistence across add-on restart

## Failure Modes

- **LM Studio down**: `/health` shows degraded; `/v1/*` returns 503 with reason. No compute attempted locally.
- **Chroma down**: embeddings proxy still returns LM Studio response; upsert attempts log error and are retried (backoff).
- **Supervisor token missing**: ToolBridge and Options persistence to add-on options will return 401. Ensure `hassio_api: true` and `homeassistant_api: true` in `config.yaml`.
