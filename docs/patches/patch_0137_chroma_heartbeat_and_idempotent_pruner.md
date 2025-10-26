# Patch 0137 – Chroma heartbeat and idempotent TTL pruner

- Chroma health now probes `/api/v2/heartbeat` first, falling back to `/api/v1/heartbeat` and legacy `/docs` responses while following redirects to avoid false negatives.
- The TTL prune scheduler runs through an idempotent background thread that never reuses the same `Thread` instance, preventing reload crashes and ensuring clean stop/start cycles.
