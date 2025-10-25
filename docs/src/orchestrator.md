# Orchestrator Source Doclets

## `main.py`
- Initializes FastAPI with lifespan hooks that manage shared `httpx` clients for LM hosts and Chroma.
- Loads options from `/data/options.json`, normalizes `lm_hosts`, and configures runtime globals for temperature, sampling, and Chroma mode.
- Exposes `/v1` OpenAI routes, `/api/options`, `/api/status`, and `/health`. Hot-applies options and reinitializes the Chroma client on demand.

## `mpc_server.py`
- Declares the FastAPI router mounted at `/mcp` and manages the `MPCServer` singleton.
- Coordinates WebSocket sessions, enforcing the single-writer rule for automation commands.

## `sessions.py`
- Wraps SQLite persistence with WAL mode for MPC session storage.
- Provides CRUD operations for session metadata and transcripts.
- Ensures all database writes happen inside the asyncio loop to avoid thread contention.

## `vector/chroma_client.py`
- Configures remote (`http`) or embedded Chroma clients via `ChromaConfig`.
- Implements health checks, collection retrieval, and embedding upserts.
- Handles error logging so operators can differentiate between connectivity failures and data validation issues.
