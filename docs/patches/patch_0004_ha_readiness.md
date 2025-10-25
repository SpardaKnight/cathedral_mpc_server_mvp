# Patch 0004: Final HA add-on readiness fixes

## Summary
- extend the LM Studio HTTP client pool to use explicit streaming-safe timeouts so SSE responses stay open for long chats
- ensure embedded Chroma mode bootstraps its persistence directory before initializing the client
- update the Home Assistant add-on manifest with dual-mode Chroma options and the upsert toggle

## Verification
- `python -m compileall cathedral_orchestrator/orchestrator`
