# Cathedral Orchestrator MegaDoc

## Overview
Cathedral Orchestrator is the Home Assistant add-on that fronts Cathedral's OpenAI-compatible relay and multi-party control (MPC) server. The add-on proxies Chat Completions and Embeddings requests to user-supplied LM Studio or OpenAI-compatible hosts, manages stateful MPC WebSocket sessions, and stores vectors through Chroma. All runtime state adheres to the single-writer rule: the add-on is the only process mutating `/data/sessions.db` and `/data/chroma` to guarantee consistency across Supervisor restarts.

## Add-on Layout
```
repo root
├── README.md                # entrypoint, links to docs/
├── cathedral_orchestrator/  # Home Assistant add-on folder
│   ├── Dockerfile           # Debian bookworm base, venv bootstrap + Supervisor labels
│   ├── build.yaml           # Supervisor build matrix override for amd64 bookworm
│   ├── config.yaml          # Supervisor-facing manifest
│   ├── config.json          # JSON mirror of the manifest
│   ├── translations/        # Add-on UI labels surfaced in Supervisor
│   └── orchestrator/        # application package (FastAPI + MPC)
├── docs/                    # MegaDoc, schema, specs, operations, patch logs
└── dev/                     # opt-in local environment mirror
```

## Runtime Surface
* **HTTP 8001/tcp** – OpenAI-compatible REST endpoints: `/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, plus `/api/options`, `/api/status`, `/health`, and `/debug/probe`. `/v1/models` enriches each model with LM Studio-provided context window and embedding hints so desktop clients (AnythingLLM, LM Studio) can auto-size prompts. Chat completions now enforce `text/event-stream`, detect client disconnects, apply idle timeouts, and synthesize `data: [DONE]` frames when upstream stalls.
* **WebSocket 5005/tcp** – MPC WebSocket server mounted under `/mcp`. Handles Cathedral tool flows and applies the single-writer constraint for automations.
* **Supervisor APIs** – `/api/options` accepts JSON payloads to hot-apply configuration; `/api/status` surfaces current options for troubleshooting.

`/api/status` merges all configured LM hosts into a single model catalog, reports per-host health, exposes LM/Chroma readiness, and tracks active session counts so operators can confirm routing, host affinity, and Chroma collection provisioning at a glance. `/debug/probe` triggers an immediate host refresh with per-host counts and the most recent error class/message so operators can validate connectivity without waiting for the background loop.

The Home Assistant watchdog is configured for `tcp://[HOST]:[PORT:8001]`. A resilient background bootstrap loop now refreshes LM hosts, model catalogs, and readiness flags without blocking startup, so the API remains available even if LM Studio is offline. The s6 `start.sh` probe logs warnings when hosts are unreachable but proceeds to launch Uvicorn immediately, relying on the background loop to finalize readiness. `/health` continues to gate Supervisor readiness and reports `bootstrap_pending` until probes succeed.

## Options Schema (authoritative)
| Option | Type | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `lm_hosts` | list(url) | Yes | `[]` | Ordered list of language model base URLs. Trailing `/v1` is stripped automatically. | `[]` |
| `chroma_mode` | enum (`http`) | Yes | `"http"` | HTTP-only mode. Supervisor schema mirrors this as a string enum. | `"http"` |
| `chroma_url` | url? | Conditional | `"http://127.0.0.1:8000"` | Remote Chroma endpoint used when `chroma_mode` is `"http"`. | `"http://192.168.1.42:8000"` |
| `collection_name` | str | Yes | `"cathedral"` | Chroma collection that stores embeddings for the orchestrator. | `"cathedral"` |
| `allowed_domains` | list(str) | Yes | `["light","switch","scene"]` | Home Assistant domains exposed to MPC tools. | `["light","switch","scene","media_player"]` |
| `temperature` | float | Yes | `0.7` | Default sampling temperature applied to LM Studio compatible hosts. | `0.6` |
| `top_p` | float | Yes | `0.9` | Default nucleus sampling value passed through to upstream models. | `0.85` |
| `upserts_enabled` | bool | Yes | `true` | Enables real-time embedding upserts to Chroma. Disable to operate in read-only replay mode. | `false` |
| `auto_config` | bool | Yes | `true` | Allows MPC auto-configuration to hot-apply LM/Chroma settings from AnythingLLM. | `true` |
| `auto_discovery` | bool | Yes | `false` | Enables LAN LM host discovery and merges unlocked hosts into the catalog automatically. | `true` |
| `lock_hosts` | bool | Yes | `false` | Prevents remote updates from altering `lm_hosts`. | `false` |
| `lock_LMSTUDIO_BASE_PATH` | bool | Yes | `false` | Blocks MPC auto-config from rewriting the LM Studio base path. | `false` |
| `lock_EMBEDDING_BASE_PATH` | bool | Yes | `false` | Locks the embedding base path for remote config pushes. | `false` |
| `lock_CHROMA_URL` | bool | Yes | `false` | Locks the Chroma URL for remote config pushes. | `false` |
| `lock_VECTOR_DB` | bool | Yes | `false` | Locks vector database selection and blocks `chroma_mode` rewrites during remote config pushes. | `false` |

Full schema guidance lives in [docs/schemas/ADDON_OPTIONS.md](schemas/ADDON_OPTIONS.md).

## Chroma Mode
* **HTTP mode only**: vectors are proxied to the remote Chroma deployment identified by `chroma_url`. The orchestrator proactively creates the configured collection when options change or sessions bootstrap and records the collection ID alongside each MPC session. Session host affinity keeps MPC clients bound to their assigned LM host, and `/api/status` reflects host health, catalog entries, and active sessions for operators.

## LM Studio Contract
* Provide base URLs **without** `/v1` in the add-on options. The orchestrator appends `/v1/...` when routing embeddings and model discovery requests; chat completions stream through the first configured LM host using the same async pass-through so Server-Sent Events reach AnythingLLM unchanged.
* LM Studio’s embeddings endpoint expects GPU acceleration on Windows; specify hosts that expose `/v1/embeddings` or disable embeddings for read-only flows.
* Multiple hosts are pooled; the orchestrator selects the first host that advertises the requested `model` from `/v1/models`. The `/api/v0/models` surface now unions the per-host inventories (with context metadata) so LM Studio's REST bridge and AnythingLLM's probes see a single aggregated catalog.

## Concurrency
* Server-Sent Events enforce `text/event-stream`, monitor client disconnects, and enforce a five-minute idle timeout. The relay injects `data: [DONE]` when upstreams terminate without sending the sentinel so clients do not hang.
* LM HTTP clients are shared across requests with `max_connections=100` and `max_keepalive_connections=20` to balance concurrency and memory footprint, while host discovery and catalog refreshes spin up fresh, short-lived HTTPX clients per host so a timeout on one base never poisons the others. Streaming relays still reuse the long-lived pool with unlimited read windows.
* Uvicorn runs with `uvloop` and `httptools` (provided by the add-on image) for efficient async dispatch. MPC WebSocket sessions share the same event loop, and SQLite writes rely on WAL mode to avoid blocking.

## Security
* Supervisor supplies the add-on token via environment; the orchestrator never emits the token or LLAT to logs. Only LAN addresses should reach ports `8001` and `5005`.
* Optionally terminate TLS or proxy authentication upstream (e.g., via Nginx) if exposing beyond the LAN. The add-on itself does not inject auth prompts.
* MCP `/mcp` routes accept requests from Home Assistant core only; external tool invocations should traverse Supervisor’s API proxy.

## Install / Upgrade
1. Add the custom repository to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**. Use `https://github.com/SpardaKnight/cathedral_mpc_server_mvp` (no `.git` suffix).
2. After adding, select **⋮ → Reload** in the Add-on Store to force a refresh; the store search does not auto-index custom repositories.
3. Install *Cathedral Orchestrator* from the *Cathedral* section. For private installs, place the repository under `/addons/cathedral_orchestrator` inside the Supervisor file editor and reload the store.
4. Upgrades follow Supervisor’s version bump. Increment `version` in `config.yaml`/`config.json` when publishing updates so the Add-on Store surfaces an Update button and Supervisor rebuilds the container automatically.

## Build & Base
* `build.yaml` pins the Supervisor build to `ghcr.io/home-assistant/amd64-base-debian:bookworm` as the single source for Supervisor builds.
* `Dockerfile` creates a virtual environment at `/opt/venv`, installs pinned Python packages (FastAPI, Uvicorn, HTTPX, Chroma, etc.), and copies application sources into `/opt/app/orchestrator`.
* Supervisor builds images with `docker buildx build` under BuildKit. Operators can mirror the exact invocation (see [operations/smoke-build.md](operations/smoke-build.md)) to confirm the image constructs without running runtime tests.

## MCP
* Handshake advertises the full handled scope set: `session.*`, `memory.*`, `prompts.*`, `config.*`, `sampling.*`, `resources.*`, `agents.*`, and `voice.*`. Tooling continues to delegate `tools.*` to the Home Assistant Supervisor proxy.
* Implements MPC config scopes including `config.read` and `config.read.result`; the latter hot-applies unlocked LM/Chroma settings to `/api/options` when `auto_config` is enabled.
* `agents.list` exposes the orchestrator agent metadata alongside all persona template IDs discovered under `/data/personas`. `agents.resurrect` resets a persona's runtime state to its template.
* `resources.list` and `resources.health` surface the merged model catalog and per-host health derived from `/api/status`.
* MPC sessions remain single-writer but now record the assigned host, model ID, and Chroma collection metadata as part of the session bootstrap.
* `voice.speak` proxies text to a Wyoming-compatible TTS endpoint (default `127.0.0.1:8181`) and returns base64-encoded PCM audio so Home Assistant can forward spoken responses.

## Persona Management
Persona templates live under `/data/personas` as YAML or JSON files. Each persona is hydrated on startup and tracked independently from its on-disk template so runtime mutations never overwrite the original definition. When MPC clients request `session.create`, the orchestrator validates the requested `persona_id` and falls back to the `default` persona if a template is missing. Operators or automations can invoke `agents.resurrect` to reset a persona's runtime state back to the template without restarting the add-on.

## Voice Integration
The orchestrator exposes a `voice.*` MPC scope that relays synthesized audio from a Wyoming-compatible TTS service. By default the proxy connects to `127.0.0.1:8181`, writes the UTF-8 encoded text length-prefixed over TCP, and streams the PCM payload back to the caller. Responses include base64-encoded audio and a `pcm` format marker so downstream Home Assistant flows can convert or play the result immediately. Errors (missing text, network failures) are logged and surfaced to MPC clients with structured error codes.

## Known Foot-guns
* Early schema revisions accepted `lm_hosts` as a dict; ensure the current list-of-URL schema is used to avoid validation errors.
* Alpine/musl bases break `onnxruntime` wheels bundled with Chroma. Stick with Debian Bookworm to avoid segmentation faults.
* Home Assistant store search ignores custom repositories until the store is manually reloaded. If the add-on is missing, trigger **Reload** again or verify network connectivity.

## Operator Quickstart
```bash
# List models discovered across LM hosts
curl -s http://homeassistant.local:8001/v1/models | jq

# Embed a prompt via orchestrator
curl -s http://homeassistant.local:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "Cathedral status", "model": "<your-embed-model-id>"}'

# Hot-apply configuration while Supervisor persists options separately
curl -s http://homeassistant.local:8001/api/options \
  -H "Content-Type: application/json" \
  -d '{"lm_hosts": ["http://192.168.1.233:1234"]}'

# Health probe summarizing LM reachability and Chroma mode
curl -s http://homeassistant.local:8001/health | jq

# On-demand host probe with error diagnostics
curl -s http://homeassistant.local:8001/debug/probe | jq
```

Remember: only one orchestrator instance should write to the shared `/data` volume to maintain consistency.
