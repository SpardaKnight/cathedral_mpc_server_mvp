# Patch 0175: MPC session handshake and HA token preference

## Summary
- Implement `session.handshake` and `session.resume` in the MPC server.
- Verify HA long-lived tokens via Supervisor `/core/api` and adopt them in ToolBridge only on success.
- ToolBridge adds `_auth_headers`, `verify_ha_token`, and `set_long_lived_token`, preferring the verified token.
- No logging of secrets. Service discovery cache resets on token change.

## Testing
- ruff check cathedral_orchestrator/orchestrator clients custom_components
- mypy cathedral_orchestrator/orchestrator
- Manual:
  - wscat -c ws://ADDON_HOST:5005/mcp
    - `{"id":"1","scope":"session.handshake","workspace_id":"default","payload":{"ha_token":"<REDACTED>"}}`
      - Expect ok:true with `session_id`
    - `{"id":"2","scope":"tools.list"}`
      - Expect tools populated under the adopted token.
    - `{"id":"3","scope":"session.resume","workspace_id":"default","thread_id":"<from session_id>"}`
      - Expect ok:true.
