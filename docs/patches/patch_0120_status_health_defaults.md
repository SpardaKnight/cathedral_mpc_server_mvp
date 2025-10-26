# Patch 0120 – Status payload shape, health readiness, auto-config defaults

## Summary
- Return model catalog as `{host_url: [model_id, ...]}` from `/api/status` per Cathedral v3.1 and document the contract.
- Tighten `/health` readiness so add-on reports `503` until LM clients are connected and at least one host is configured.
- Default `auto_config` to `true` across manifests and schema docs while keeping other locks/discovery flags `false`.
- Gate the Docker smoke test on CLI availability to keep test runs green when Docker is not installed.

## Affected Artifacts
- `cathedral_orchestrator/orchestrator/main.py`
- `cathedral_orchestrator/config.yaml`
- `cathedral_orchestrator/config.json`
- `cathedral_orchestrator/orchestrator/logging_config.py`
- `cathedral_orchestrator/orchestrator/sse.py`
- `cathedral_orchestrator/orchestrator/toolbridge.py`
- `README.md`
- `docs/schemas/ADDON_OPTIONS.md`
- `cathedral_orchestrator/CHANGELOG.md`
- `tests/test_addon_installation.py`
- `custom_components/cathedral_agent/__init__.py`
- `custom_components/cathedral_agent/conversation.py`
- `custom_components/cathedral_mpc/coordinator.py`
- `custom_components/cathedral_mpc/number.py`
- `custom_components/cathedral_mpc/select.py`
- `custom_components/cathedral_mpc/switch.py`
- `custom_components/cathedral_mpc/config_flow.py`
- `custom_components/cathedral_mpc/options_flow.py`
- `cathedral_orchestrator/orchestrator/mpc_server.py`
- `mypy.ini`
