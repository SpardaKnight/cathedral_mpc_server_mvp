# Patch 0148 — Supervisor alignment follow-up

## Summary

- Synced the Home Assistant add-on manifest defaults and schema comments with the Supervisor-mandated wording for the 0.1.2 release.
- Confirmed the JSON manifest mirrors the watchdog, port descriptions, and schema primitives required by the Supervisor validator.
- Left the orchestrator runtime, Docker build, and readiness scripts unchanged while ensuring their surrounding metadata matches the published spec.

## Testing

- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
