# Patch 0147 – Manifest alignment, watchdog, translations, readiness gating

## Summary
- Synced the Home Assistant add-on manifests (YAML + JSON) with version 0.1.2, tcp watchdog target, and port descriptions.
- Ensured the Debian build base and Dockerfile labels match Supervisor expectations with `netcat-openbsd` for readiness probes.
- Refined startup gating, readiness telemetry, and UI translations to meet HA review requirements.

## Verification
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
