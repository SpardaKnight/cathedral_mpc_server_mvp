# Error Recovery Specification

## LM Host Failures
- Each LM request logs `lm_models_fail` when `/v1/models` probing fails. Operators should check Supervisor logs for the host URL and underlying exception string. Hostpool refreshes now include the exception class name and retain the latest probe snapshot for diagnostics.
- During chat completion errors, the orchestrator relays upstream HTTP status codes. Clients receive the original error body when available.
- If all hosts fail discovery, `_route_for_model` falls back to the first configured host; missing models yield upstream 404s.
- `/debug/probe` is available for manual verification. It spawns fresh HTTPX clients per host to avoid reusing poisoned connections, returning per-host counts and failure metadata immediately.

## Chroma Upsert Errors
- Chroma upserts run through `vector/chroma_client.py`. Exceptions during `upsert` emit structured logs with error context.
- When remote Chroma becomes unavailable, the health check exposes `{ "chroma": { "ok": false } }`. Operators can switch to embedded mode via `/api/options` hot-apply.
- Embedded Chroma I/O failures surface as Python exceptions; restart after validating disk space and permissions on `/data/chroma`.

## LM Host Fallback Strategy
- `_normalize_lm_hosts` strips `/v1` and builds a deterministic host map. When no host advertises the requested model, the orchestrator selects the first host in configuration order.
- Operators can prioritize hosts by ordering within `lm_hosts`. Update the list and POST to `/api/options` to reprioritize without restart.

## Health Paths
- `/health` returns HTTP 503 until HTTPX clients are initialized. After startup, it reports per-host model counts and Chroma readiness.
- `/api/status` includes a Unix timestamp so operators can confirm the add-on is running and responding.

## Tool Failures
- Tool execution exceptions within `ToolBridge` propagate to MPC clients with error details while logging via `jlog`.
- Persistent tool failures typically indicate Home Assistant service misconfiguration; verify the target domains remain in `allowed_domains`.
