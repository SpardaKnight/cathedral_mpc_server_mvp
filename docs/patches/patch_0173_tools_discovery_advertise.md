# Patch 0173: HA tools discovery + MPC advertisement

## Summary
- Introduce `ToolBridge.list_services()` that fetches Home Assistant `/core/api/services` through Supervisor with TTL caching.
- MPC server now includes `tools` in `agents.list` and implements `tools.list` for explicit enumeration.
- Options reload invalidates the tools cache when `allowed_domains` change.

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit (if present)
- Manual:
  - wscat to /mcp: send {"id":"1","scope":"agents.list"} and verify "tools" populated.
  - wscat to /mcp: send {"id":"2","scope":"tools.list"} and verify tools array.
  - Trigger a service: {"id":"3","scope":"tools.call","name":"light.turn_on","payload":{"entity_id":"light.kitchen"}} and verify state change in HA.
  - POST /api/options with a different allowed_domains and confirm ha_services_discovered and refreshed tool set.
