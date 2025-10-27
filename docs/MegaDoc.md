# Cathedral Orchestrator MegaDoc

## Overview
Cathedral Orchestrator is the Home Assistant add-on that fronts Cathedral's OpenAI-compatible relay and multi-party control (MPC) server. The add-on proxies Chat Completions and Embeddings requests to user-supplied LM Studio or OpenAI-compatible hosts, manages stateful MPC WebSocket sessions, and stores vectors through Chroma. All runtime state adheres to the single-writer rule: the add-on is the only process mutating `/data/sessions.db` and `/data/chroma` to guarantee consistency across Supervisor restarts.

## Add-on Layout
```
repo root
├── README.md                # entrypoint, links to docs/
├── cathedral_orchestrator/  # Home Assistant add-on folder
│   ├── Dockerfile           # Debian bookworm base, venv bootstrap + Supervisor labels
│   ├── build.json           # Supervisor build metadata (arch, base)
│   ├── build.yaml           # Supervisor build matrix override for amd64 bookworm
│   ├── config.yaml          # Supervisor-facing manifest
│   ├── config.json          # JSON mirror of the manifest
│   ├── translations/        # Add-on UI labels surfaced in Supervisor
│   └── orchestrator/        # application package (FastAPI + MPC)
├── docs/                    # MegaDoc, schema, specs, operations, patch logs
└── dev/                     # opt-in local environment mirror
```

## Runtime Surface
* **HTTP 8001/tcp** – OpenAI-compatible REST endpoints: `/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, plus `/api/options`, `/api/status`, and `/health`. Chat completions now enforce `text/event-stream`, detect client disconnects, apply idle timeouts, and synthesize `data: [DONE]` frames when upstream stalls.
* **WebSocket 5005/tcp** – MPC WebSocket server mounted under `/mcp`. Handles Cathedral tool flows and applies the single-writer constraint for automations.
* **Supervisor APIs** – `/api/options` accepts JSON payloads to hot-apply configuration; `/api/status` surfaces current options for troubleshooting.

`/api/status` merges all configured LM hosts into a single model catalog, reports per-host health, exposes LM/Chroma readiness, and tracks active session counts so operators can confirm routing, host affinity, and Chroma collection provisioning at a glance.

## Options Schema (authoritative)
| Option | Type | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `lm_hosts` | list(url) | Yes | `[]` | Ordered list of language model base URLs. Trailing `/v1` is stripped automatically. | `[]` |
| `chroma_mode` | enum (`http`) | Yes | `"http"` | HTTP-only mode. Supervisor schema uses `list(http)` to restrict values. | `"http"` |
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
| `lock_VECTOR_DB` | bool | Yes | `false` | Locks vector database selection for remote config pushes. | `false` |

Full schema guidance lives in [docs/schemas/ADDON_OPTIONS.md](schemas/ADDON_OPTIONS.md).

## Chroma Mode
* **HTTP mode only**: vectors are proxied to the remote Chroma deployment identified by `chroma_url`. The orchestrator proactively creates the configured collection when options change or sessions bootstrap and records the collection ID alongside each MPC session. Session host affinity keeps MPC clients bound to their assigned LM host, and `/api/status` reflects host health, catalog entries, and active sessions for operators.

## LM Studio Contract
* Provide base URLs **without** `/v1` in the add-on options. The orchestrator appends `/v1/...` when routing embeddings and model discovery requests; chat completions stream through the first configured LM host using the same async pass-through so Server-Sent Events reach AnythingLLM unchanged.
* LM Studio’s embeddings endpoint expects GPU acceleration on Windows; specify hosts that expose `/v1/embeddings` or disable embeddings for read-only flows.
* Multiple hosts are pooled; the orchestrator selects the first host that advertises the requested `model` from `/v1/models`.

## Concurrency
* Server-Sent Events enforce `text/event-stream`, monitor client disconnects, and enforce a five-minute idle timeout. The relay injects `data: [DONE]` when upstreams terminate without sending the sentinel so clients do not hang.
* LM HTTP clients are shared across requests with `max_connections=100` and `max_keepalive_connections=20` to balance concurrency and memory footprint.
* Uvicorn runs with `uvloop` and `httptools` (provided by the add-on image) for efficient async dispatch. MPC WebSocket sessions share the same event loop, and SQLite writes rely on WAL mode to avoid blocking.

## Security
* Supervisor supplies the add-on token via environment; the orchestrator never emits the token or LLAT to logs. Only LAN addresses should reach ports `8001` and `5005`.
* Optionally terminate TLS or proxy authentication upstream (e.g., via Nginx) if exposing beyond the LAN. The add-on itself does not inject auth prompts.
* MCP `/mcp` routes accept requests from Home Assistant core only; external tool invocations should traverse Supervisor’s API proxy.

## Install / Upgrade
1. Add the custom repository to Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**. Use `https://github.com/SpardaKnight/cathedral_mpc_server_mvp` (no `.git` suffix).
2. After adding, select **⋮ → Reload** in the Add-on Store to force a refresh; the store search does not auto-index custom repositories.
3. Install *Cathedral Orchestrator* from the *Cathedral* section. For private installs, place the repository under `/addons/cathedral_orchestrator` inside the Supervisor file editor and reload the store.
4. Upgrades follow Supervisor’s version bump. Increment `version` in `config.yaml`/`config.json` when publishing updates; Supervisor rebuilds the container automatically.

## Build & Base
* `build.yaml` pins the Supervisor build to `ghcr.io/home-assistant/amd64-debian:bookworm`; `build.json` retains the legacy multi-arch map for reference.
* `Dockerfile` creates a virtual environment at `/opt/venv`, installs pinned Python packages (FastAPI, Uvicorn, HTTPX, Chroma, etc.), and copies application sources into `/opt/app/orchestrator`.
* Supervisor builds images with `docker buildx build` under BuildKit. Operators can mirror the exact invocation (see [operations/smoke-build.md](operations/smoke-build.md)) to confirm the image constructs without running runtime tests.

## MCP
* Implements MPC config scopes including `config.read` and `config.read.result`; the latter hot-applies unlocked LM/Chroma settings to `/api/options` when `auto_config` is enabled.
* `resources.list` and `resources.health` now surface the merged model catalog and per-host health derived from `/api/status`.
* MPC sessions remain single-writer but now record the assigned host, model ID, and Chroma collection metadata as part of the session bootstrap.

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
```

Remember: only one orchestrator instance should write to the shared `/data` volume to maintain consistency.
