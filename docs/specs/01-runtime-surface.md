# Runtime Surface Specification

## HTTP Endpoints (port 8001)

| Path | Method | Description | Request Body | Response | Notes |
| --- | --- | --- | --- | --- | --- |
| `/v1/models` | GET | Lists models from all configured LM hosts with LM Studio context metadata. | None | `{ "object": "list", "data": [...] }` aggregated from upstream hosts. | Returns 503 if HTTP client pool not ready. Each entry includes `context_length`, `max_input_tokens`, and optional `embedding_length` when LM Studio publishes them. |
| `/api/v0/models` | GET | LM Studio-compatible REST catalog union. | None | `{ "loaded": [...], "downloaded": [] }` with per-model context hints. | Passes through to the single configured host or synthesizes a union across multiple hosts with metadata harvested during catalog refreshes. |
| `/v1/chat/completions` | POST | Relays OpenAI Chat Completions to LM Studio. | OpenAI-compatible JSON (with optional `stream`). | Streaming SSE response from the first configured LM host (same base catalogued by `/api/v0/models`). | Forwards raw `text/event-stream` packets exactly as received from LM Studio. |
| `/v1/embeddings` | POST | Proxies embeddings requests. | `{ "input": ..., "model": ... }` | JSON embedding payload from selected host. | Chooses host via `_route_for_model`; falls back to first host configured. |
| `/api/options` | GET | Returns current runtime options. | None | JSON options map matching Supervisor schema. | Used for diagnostics. |
| `/api/options` | POST | Hot-applies new options. | JSON subset matching schema. | `{ "ok": true, "applied": {...} }` | Updates LM host map and reinitializes Chroma client in-place. Persist via Supervisor API for restart durability. |
| `/api/status` | GET | Exposes timestamp and active options. | None | `{ "ts": <unix>, "options": {...} }` | Internal status view. |
| `/health` | GET | Aggregated health probe. | None | `{ "ok": true, "lm_hosts": {...}, "chroma": {...} }` | Fan-out to all LM hosts plus Chroma `.health()`. Returns 503 when HTTP client pool not ready. |
| `/debug/probe` | GET | Triggers an immediate LM host probe. | None | `{ "hosts": [{"host": ..., "model_count": ..., "status": ..., "detail": {...}}] }` | Uses per-host short-lived HTTPX clients so one failure cannot poison other connections. |

## WebSocket + MPC (port 5005)

* `/mcp` – Primary MPC WebSocket endpoint served by `MPCServer`. Clients must authenticate through Home Assistant. Supports streaming automation commands and responses.

MPC WebSocket sessions share the same asyncio event loop as FastAPI. Sessions persist state in `/data/sessions.db` and rely on SQLite WAL mode for concurrent reads.

## SSE Terminators

For streaming chat completions, the orchestrator relays upstream SSE packets unmodified. The stream concludes when the upstream payload equals `data: [DONE]\n\n`. Keep-alive heartbeats from upstream models are forwarded downstream.

## Hot-apply Semantics

`POST /api/options` immediately:
1. Normalizes `lm_hosts` to a deterministic map.
2. Reinitializes the Chroma client with updated mode/URL/persist directory.
3. Updates `ToolBridge.allowed_domains` and toggles upsert behavior.

Changes take effect for subsequent requests without restarting the add-on, but operators must also persist the new options via the Supervisor API so restarts reload the same values.
