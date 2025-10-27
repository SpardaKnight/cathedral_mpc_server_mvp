# Patch 0146 – HA 0.1.2 watchdog, catalog telemetry, and manifest sync

## Summary
- Updated the add-on build metadata to rely on `build.yaml` with Home Assistant's Debian base and Supervisor labels.
- Synchronized YAML/JSON manifests with tcp watchdog, port descriptions, and schema corrections alongside refreshed UI translations.
- Hardened startup, readiness telemetry, SSE relay guarantees, and MPC session assignments while documenting the changes across changelogs and the MegaDoc.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
