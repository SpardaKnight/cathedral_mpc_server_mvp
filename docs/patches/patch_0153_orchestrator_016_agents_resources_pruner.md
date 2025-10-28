# Patch 0153 – Orchestrator 0.1.6 stabilization

- Restore AnythingLLM discovery by expanding the MPC `agents.*` family to advertise handled/delegated scopes, stable `params`, and a 1.2 handshake identifier.
- Normalize `resources.list` / `resources.health` so clients receive the catalog under both `catalog` and `hosts` keys plus timestamped readiness telemetry.
- Replace the idle session prune runner with a synchronous SQLite delete to avoid `threads can only be started once` when reloading the add-on.
- Harden Chroma collection bootstrap with a v2-first lookup/create flow (with v1 fallback) and structured logs for each branch, ensuring re-embeds succeed after unload.
- Bump Supervisor manifests and CHANGELOG to 0.1.6 to surface the release in Home Assistant.
