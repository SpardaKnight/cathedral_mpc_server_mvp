# Concurrency Specification

## HTTP Client Strategy
- A shared `httpx.AsyncClient` handles LM requests with `max_connections=100` and `max_keepalive_connections=20` to balance concurrency and upstream pressure.
- Timeouts use `httpx.Timeout(connect=30, write=30, read=None, pool=None)` so SSE streams remain open until upstream completion.

## SSE Streaming
- Chat Completions default to streaming responses. The orchestrator relays upstream `data:` frames unchanged.
- Keep-alive heartbeats from LM Studio are propagated, preventing idle timeouts at the client level.

## Uvicorn Execution Model
- Uvicorn runs inside the Debian-based container with `uvloop` and `httptools`, matching the `[standard]` extra installed in the virtual environment.
- The app and MPC server share a single event loop; concurrency is achieved via asyncio tasks rather than worker processes to keep state in-memory.

## MPC Sessions
- `MPCServer` enforces a single-writer policy for automations. Incoming commands are queued and executed sequentially per session.
- SQLite runs in WAL mode via `sessions.py`, allowing concurrent readers while writes serialize through the asyncio loop.

## Client Pools
- The Chroma client keeps its own `httpx.AsyncClient` with matching connection limits for remote mode.
- Embedded Chroma runs in-process; concurrency is limited by Python threads within the library and inherits WAL behavior for persistence.
