# Patch 0152 – MPC `agents.*` restoration and resource shape normalization

## Summary
- Restore `agents.*` handlers and handshake advertising.
- `agents.list` returns a deterministic Cathedral agent with capabilities.
- `resources.list` returns both `catalog` and `hosts` for compatibility.
- No change to SSE relay from 0.1.4.

## Notes
- AnythingLLM’s agent picker relies on `agents.list`.
- Tools continue to flow through ToolBridge (`tools.*`).

## QA
- Confirm the agent picker sees "Cathedral" and tools execute.
- `resources.list` shows models under both `catalog` and `hosts`.
