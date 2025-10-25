# Cathedral Orchestrator MegaDoc

## Overview
Cathedral Orchestrator is the Home Assistant add-on that fronts Cathedral's OpenAI-compatible relay and multi-party control (MPC) server. The add-on proxies Chat Completions and Embeddings requests to user-supplied LM Studio or OpenAI-compatible hosts, manages stateful MPC WebSocket sessions, and stores vectors through Chroma. All runtime state adheres to the single-writer rule: the add-on is the only process mutating `/data/sessions.db` and `/data/chroma` to guarantee consistency across Supervisor restarts.

## Add-on Layout
```
repo root
├── README.md                # entrypoint, links to docs/
├── cathedral_orchestrator/  # Home Assistant add-on folder
│   ├── Dockerfile           # Debian bookworm base, venv bootstrap
│   ├── build.json           # Supervisor build metadata (arch, base)
│   ├── config.yaml          # Supervisor-facing manifest
│   ├── config.json          # JSON mirror of the manifest
│   ├── run.sh               # container entrypoint (Supervisor-managed)
│   └── orchestrator/        # application package (FastAPI + MPC)
├── docs/                    # MegaDoc, schema, specs, operations, patch logs
└── dev/                     # opt-in local environment mirror
```

## Runtime Surface
* **HTTP 8001/tcp** – OpenAI-compatible REST endpoints: `/v1/models`, `/v1/chat/completions`, `/v1/embeddings`, plus `/api/options` for hot configuration and `/health` for readiness checks.
* **WebSocket 5005/tcp** – MPC WebSocket server mounted under `/mcp`. Handles Cathedral tool flows and applies the single-writer constraint for automations.
* **Supervisor APIs** – `/api/options` accepts JSON payloads to hot-apply configuration; `/api/status` surfaces current options for troubleshooting.

## Options Schema (authoritative)
| Option | Type | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `lm_hosts` | list(url) | Yes | `[]` | Ordered list of language model base URLs. Trailing `/v1` is stripped automatically. | `["http://192.168.1.233:1234"]` |
| `chroma_mode` | str (`"http"\|"embedded"`) | Yes | `"http"` | Determines whether vectors are proxied to a remote Chroma HTTP server or stored in the embedded engine. | `"embedded"` |
| `chroma_url` | str? | Conditional | `"http://127.0.0.1:8000"` | Remote Chroma endpoint used when `chroma_mode` is `"http"`. Ignored for embedded mode. | `"http://192.168.1.42:8000"` |
| `chroma_persist_dir` | str? | Conditional | `"/data/chroma"` | Filesystem directory for embedded Chroma persistence. Required when `chroma_mode` is `"embedded"`. | `"/data/chroma"` |
| `collection_name` | str | Yes | `"cathedral"` | Chroma collection that stores embeddings for the orchestrator. | `"cathedral"` |
| `allowed_domains` | list(str) | Yes | `["light","switch","scene"]` | Home Assistant domains exposed to MPC tools. | `["light","switch","scene","media_player"]` |
| `temperature` | float | Yes | `0.7` | Default sampling temperature applied to LM Studio compatible hosts. | `0.6` |
| `top_p` | float | Yes | `0.9` | Default nucleus sampling value passed through to upstream models. | `0.85` |
| `upserts_enabled` | bool | Yes | `true` | Enables real-time embedding upserts to Chroma. Disable to operate in read-only replay mode. | `false` |

Full schema guidance lives in [docs/schemas/ADDON_OPTIONS.md](schemas/ADDON_OPTIONS.md).

## Chroma Modes
* **HTTP mode** (default): the add-on forwards vector reads/writes to a remote Chroma deployment identified by `chroma_url`. `/health` reports the number of models discovered per LM host and whether the remote Chroma responded.
* **Embedded mode**: the add-on runs Chroma in-process, persisting data under `/data/chroma`. Ensure Supervisor mounts enough disk. The health endpoint inspects the embedded client and reports readiness without issuing network calls.

## LM Studio Contract
* Provide base URLs **without** `/v1` in the add-on options. The orchestrator appends `/v1/...` when routing requests.
* LM Studio’s embeddings endpoint expects GPU acceleration on Windows; specify hosts that expose `/v1/embeddings` or disable embeddings for read-only flows.
* Multiple hosts are pooled; the orchestrator selects the first host that advertises the requested `model` from `/v1/models`.

## Concurrency
* Server-Sent Events use `read=None` in the HTTPX timeout to keep streams open until upstream completion. Keep-alive heartbeats prevent idle disconnects.
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
* `build.json` pins the add-on to Debian Bookworm via `ghcr.io/home-assistant/amd64-debian:bookworm`.
* `Dockerfile` creates a virtual environment at `/opt/venv`, installs pinned Python packages (FastAPI, Uvicorn, HTTPX, Chroma, etc.), and copies application sources into `/opt/orchestrator`.
* Supervisor builds images with `docker buildx build` under BuildKit. Operators can mirror the exact invocation (see [operations/smoke-build.md](operations/smoke-build.md)) to confirm the image constructs without running runtime tests.

## MCP
* Implements MCP scopes `config.read` and `config.write` so Cathedral clients can fetch and persist Home Assistant tool settings.
* MPC sessions are single-writer; the orchestrator enforces sequential command execution and streams updates via `/mcp/ws` with SSE fallbacks.
* Expect the server to be ready to apply writes immediately after `/health` returns `{"ok": true}`.

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
  -d '{"input": "Cathedral status", "model": "text-embedding-3-large"}'

# Hot-apply configuration while Supervisor persists options separately
curl -s http://homeassistant.local:8001/api/options \
  -H "Content-Type: application/json" \
  -d '{"lm_hosts": ["http://192.168.1.233:1234"]}'

# Health probe summarizing LM reachability and Chroma mode
curl -s http://homeassistant.local:8001/health | jq
```

Remember: only one orchestrator instance should write to the shared `/data` volume to maintain consistency.
