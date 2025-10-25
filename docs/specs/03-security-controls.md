# Security Controls Specification

## Network Posture
- Ports `8001/tcp` (HTTP) and `5005/tcp` (WebSocket MPC) are LAN-only and exposed through Home Assistant Supervisor’s ingress rules. External exposure requires an operator-managed TLS proxy.
- The add-on does not terminate TLS. Operators must deploy TLS offloaders (Nginx, Caddy, HA reverse proxy) if WAN access is required.

## Authentication & Tokens
- Supervisor injects an add-on token via environment variables. The orchestrator consumes it for Supervisor API calls but never logs or re-emits the token.
- LLAT (Long-Lived Access Tokens) are not stored in options or logs. Operators should use Supervisor-issued tokens only.

## Tool Allow-list
- `allowed_domains` in the options schema gates Home Assistant service calls. MPC tooling exposes only the whitelisted domains to Cathedral agents.
- Changes to the allow-list require `/api/options` hot-apply plus Supervisor persistence to survive restarts.

## Logging Hygiene
- Structured logs via `logging_config.py` write to Home Assistant’s log collector and avoid printing secrets.
- Error events (e.g., upstream LM failures) include host identifiers but exclude payload bodies or API keys.

## MCP Exposure
- `/mcp` routes are intended for trusted Cathedral clients living inside the HA network. If bridging to remote operators, terminate at a proxy enforcing authentication and rate limiting.
- MPC commands are serialized; concurrent writes are rejected per the single-writer rule to prevent race conditions in automations.
