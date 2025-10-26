# Cathedral Orchestrator (Home Assistant Add-on)

Cathedral Orchestrator bridges Home Assistant with Cathedral’s OpenAI-compatible relay and MPC tool stack. The add-on proxies Chat Completions and Embeddings to operator-supplied LM Studio hosts, exposes `/mcp` for Cathedral tools, and keeps vector state in Chroma (HTTP or embedded). All writes to `/data/sessions.db` and `/data/chroma` follow the single-writer rule.

- **MegaDoc**: [docs/MegaDoc.md](docs/MegaDoc.md) – complete architecture, schema, and operator guidance.
- **Smoke Build**: [docs/operations/smoke-build.md](docs/operations/smoke-build.md) – the only sanctioned validation path.
- **Agents Guide**: [AGENTS.md](AGENTS.md) – rules for code agents and release discipline.

## Quick Install (Home Assistant Supervisor)
1. Open **Settings → Add-ons → Add-on Store → ⋮ → Repositories**.
2. Add `https://github.com/SpardaKnight/cathedral_mpc_server_mvp` (no `.git`).
3. Press **⋮ → Reload** so Supervisor indexes the repository.
   (If the add-on does not appear, reload again — the global search does not index custom repositories.)
4. Install **Cathedral Orchestrator** from the *Cathedral* section (or *Local add-ons* if you copied the repo into `/addons/cathedral_orchestrator`).
5. Configure options, save, and start the add-on. Hot updates can be applied later via `POST /api/options`, but persist through the UI to survive restarts.

## Configuration Snapshot
| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `lm_hosts` | list(url) | `[]` | Base URLs for LM Studio/OpenAI-compatible hosts. Trailing `/v1` is removed automatically. |
| `chroma_mode` | `"http"` or `"embedded"` | `"http"` | Select remote Chroma or embedded persistence. |
| `chroma_url` | str? | `"http://127.0.0.1:8000"` | Required when `chroma_mode` is `"http"`. |
| `chroma_persist_dir` | str? | `"/data/chroma"` | Required when `chroma_mode` is `"embedded"`. |
| `collection_name` | str | `"cathedral"` | Chroma collection name. |
| `allowed_domains` | list(str) | `["light","switch","scene"]` | Home Assistant domains exposed to Cathedral tools. |
| `temperature` | float | `0.7` | Default sampling temperature forwarded to LM hosts. |
| `top_p` | float | `0.9` | Default nucleus sampling value. |
| `upserts_enabled` | bool | `true` | Enables vector upserts; disable for read-only mode. |
| `auto_config` | bool | `true` | Enable Supervisor-driven host/bootstrap configuration surfaced in `/api/status`. |
| `auto_discovery` | bool | `false` | Reserved toggle for LAN discovery of compatible LM hosts. |
| `lock_hosts` | bool | `false` | Prevents remote config writers from mutating `lm_hosts`. |
| `lock_LMSTUDIO_BASE_PATH` | bool | `false` | Locks MPC client overrides for LM Studio base path. |
| `lock_EMBEDDING_BASE_PATH` | bool | `false` | Locks MPC client overrides for embedding host base path. |
| `lock_CHROMA_URL` | bool | `false` | Locks MPC client overrides for the Chroma URL. |
| `lock_VECTOR_DB` | bool | `false` | Locks MPC client vector database selection.

Full schema and JSON example: [docs/schemas/ADDON_OPTIONS.md](docs/schemas/ADDON_OPTIONS.md).

`GET /api/status` exposes a **Model Catalog** keyed by host URL, where each value is a list of model identifiers available from that host. Client integrations must not expect additional metadata in the catalog payload.

Example `options` block:
```yaml
lm_hosts:
  - "http://192.168.1.233:1234"
chroma_mode: "http"
chroma_url: "http://192.168.1.42:8000"
chroma_persist_dir: "/data/chroma"
collection_name: "cathedral"
allowed_domains:
  - light
  - switch
  - scene
temperature: 0.7
top_p: 0.9
upserts_enabled: true
```

## Curl Taps
```bash
# Health probe: LM host counts + Chroma readiness
curl -s http://homeassistant.local:8001/health | jq

# Enumerate routed models
curl -s http://homeassistant.local:8001/v1/models | jq

# Embeddings relay example
curl -s http://homeassistant.local:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "status check", "model": "<your-embed-model-id>"}'
```

## Development Parity
For local work that matches the add-on image:
```bash
cd dev
./venv/activate.sh  # creates .venv with the same pins as /opt/venv
```

To mirror Supervisor’s build without running runtime tests:
```bash
make -C dev build_amd64
```

More details on build parity, security posture, concurrency, and operations live in [docs/](docs/__index__.md).

## Repository Map — Separation of Concerns

- Home Assistant add-on (server):
  addons/cathedral_orchestrator/
  → Provides MPC server at ws://<HA-IP>:5005/mcp and OpenAI relay at http://<HA-IP>:8001/v1/*
  → Handles session.*, memory.*, prompts.*, config.*, sampling.*, resources.*, agents.*; delegates tools.* to HA.

- AnythingLLM Desktop plugin (client):
  clients/anythingllm_agent_skill/cathedral-mpc-bridge/
  → Real Agent Skill that runs inside AnythingLLM Desktop (no local server).
  → Reads/writes Desktop .env and answers config.read/config.write over the MPC channel to the HA add-on.

## AnythingLLM Agent Skill — Cathedral MPC Bridge (Install & Configure)

### What this is
A real Agent Skill plugin for AnythingLLM Desktop that auto-starts a background bridge to the Cathedral Orchestrator MPC server. It does not open ports or run a server on Windows.

### Install (Windows)
1) Open Desktop storage:
   C:\Users\<YOU>\AppData\Roaming\anythingllm-desktop\storage
2) Create folder:
   plugins\agent-skills\cathedral-mpc-bridge
3) From this repo, copy into that folder:
   clients/anythingllm_agent_skill/cathedral-mpc-bridge/plugin.json
   clients/anythingllm_agent_skill/cathedral-mpc-bridge/handler.js
4) Edit handler.js and set your HA token:
   const AUTH = "Bearer <YOUR_LONG_LIVED_TOKEN_HERE>";
   (Keep the 'Bearer ' prefix.)
5) In AnythingLLM → Agent Skills → enable "Cathedral MPC Bridge".

### Configuration
- MPC endpoint (fixed): ws://homeassistant.local:5005/mcp
- The plugin reads/writes:
  %APPDATA%\anythingllm-desktop\storage\.env
- Normalized keys returned on config.read:
  LMSTUDIO_BASE_PATH, EMBEDDING_BASE_PATH, CHROMA_URL, VECTOR_DB, STORAGE_DIR
- The plugin sends orchestrator_upserts_only: true and a proactive config.read.result after connect.

### Verification
- Desktop logs show:
  [Cathedral-MPC-Bridge][info] Connected to ws://homeassistant.local:5005/mcp
- HA add-on logs show: handshake → config.read.result
- GET http://<HA-IP>:8001/v1/models returns merged model list; chat SSE ends with data: [DONE].

### Troubleshooting
- If not visible in Agent Skills, re-check the folder path:
  %APPDATA%\anythingllm-desktop\storage\plugins\agent-skills\cathedral-mpc-bridge\
- If connection fails, confirm HA add-on is running and IP/hostname is reachable.
- Ensure AUTH token is present and has not expired.
