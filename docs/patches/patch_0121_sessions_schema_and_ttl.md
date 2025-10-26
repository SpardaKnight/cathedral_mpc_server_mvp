# Patch 0121 – Session schema v3.1 extensions and TTL pruning

## Summary
- Extend `/data/sessions.db` to include v3.1 metadata columns (`host_url`, `model_id`, `health_state`, `chroma_collection_id`, `chroma_collection_name`).
- Apply idempotent migrations during orchestrator startup so existing deployments pick up the new columns without manual intervention.
- Launch a background scheduler that calls `sessions.prune_idle(ttl_minutes=120)` every 15 minutes to clean up idle threads while preserving WAL + synchronous=NORMAL.

## Migration approach
- On every SQLite connection the orchestrator executes `PRAGMA table_info` and issues `ALTER TABLE` statements for any missing v3.1 columns, logging each addition.
- New installations create the table with the full column set, and legacy rows inherit a default `health_state` of `ok` with nullable host and collection metadata.
- WAL journal mode and synchronous level remain unchanged to keep Home Assistant I/O characteristics stable.

## Scheduler and TTL
- `main._session_prune_loop` runs in the FastAPI lifespan context, invoking the new `sessions.prune_idle` helper and logging prune counts per cycle.
- Failures during pruning are caught and logged without crashing the orchestrator; cancellation during shutdown is also logged for traceability.

## Operational impact
- `/api/status` continues to report `sessions_active` via the new helper API with no schema changes, keeping dashboards untouched.
- Stale session rows aged beyond 120 minutes are reclaimed automatically, shrinking the database and Chroma linkage metadata without operator action.
- No new Supervisor options are introduced; the default TTL remains 120 minutes baked into the orchestrator runtime.
