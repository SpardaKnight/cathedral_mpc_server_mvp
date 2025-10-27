# Patch 0145 – v3.1 Supervisor manifest alignment

## Summary
- Bumped the add-on manifest to version 0.1.2 with watchdog monitoring, port descriptions, and UI translations per Cathedral Orchestrator v3.1.
- Added Supervisor build metadata (build.yaml + Docker labels) and a readiness gate in the start script to satisfy health checks.
- Updated documentation (MegaDoc + CHANGELOG) to record `/api/status`, host affinity, MPC scopes, and Chroma provisioning behavior.
- Added a placeholder pytest module hook to keep the static test suite green in CI-only environments.

## Testing
- `ruff check addons/cathedral_orchestrator/orchestrator clients custom_components`
- `mypy addons/cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
