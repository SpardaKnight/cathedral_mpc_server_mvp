# MVP Hotfix: Dockerfile pins and SQLite sessions

## Summary
- Pin the Cathedral orchestrator add-on Dockerfile dependencies without extras and ensure build tooling is present.
- Replace the in-memory style session helper with a persistent SQLite-backed implementation suitable for HA add-ons.
- Harden the embeddings endpoint input handling to normalize single strings and lists while keeping vectors aligned.

## Testing
- Pending: full acceptance test suite after local verification.
