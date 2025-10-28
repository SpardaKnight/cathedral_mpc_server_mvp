# Patch 0159 – Orchestrator 0.2.0 boot recovery and Chroma fallback hardening

## Summary
- Ship PyYAML in the add-on image and guard the optional dependency at runtime so FastAPI boots cleanly even if the wheel is missing.
- Add JSON fallback logic for persona templates and document YAML module absence in structured logs.
- Keep the Chroma client v2-first with redirect-friendly lookups while tolerating 404/405/409/410/422 responses before retrying the alternate API path.
- Bump the Supervisor manifests and CHANGELOG to 0.2.0 for visibility through the Home Assistant UI.

## Testing
- `ruff check cathedral_orchestrator/orchestrator clients custom_components`
- `mypy cathedral_orchestrator/orchestrator`
- `pytest -q tests/unit`
