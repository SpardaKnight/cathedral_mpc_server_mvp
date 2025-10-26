# Patch 0135 – Supervisor Update Visibility Audit

## Summary
- Bumped Cathedral Orchestrator add-on manifest to version 1.1.10 so Supervisor detects the latest build.
- Synced legacy JSON manifest mirror with the new version to avoid metadata drift.
- Documented the release in the changelog for Home Assistant operators.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
