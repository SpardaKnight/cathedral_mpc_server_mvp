# Data Retention Specification

## Session Database
- Located at `/data/sessions.db` inside the add-on container.
- SQLite runs in WAL mode to allow concurrent readers while MPC writes commit sequentially.
- Operators should back up `/data/sessions.db` alongside Home Assistant snapshots. Deleting the file clears active MPC session history.

## Chroma Vector Store
- Embedded mode persists vectors under `/data/chroma`. The directory includes Chroma metadata, collections, and embeddings.
- Remote HTTP mode stores vectors on the remote Chroma server and keeps no local embeddings besides transient caches.
- Include `/data/chroma` in Home Assistant snapshots or your own backup routine when using embedded mode.

## Retention Policy
- The orchestrator does not implement automatic purging. Operators decide when to prune sessions or vectors.
- Disable `upserts_enabled` to stop new embeddings from being written while retaining historical data for read-only scenarios.

## Data Migration
- Switching between HTTP and embedded mode requires manual data migration. Export vectors from the existing store before changing modes.
- Ensure disk space is sufficient before seeding `/data/chroma` to avoid write failures that impact automations.
