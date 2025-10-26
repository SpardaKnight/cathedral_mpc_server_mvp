# Patch 0124 — Static-Only Test Policy Enforcement

## Summary
- Documented the static-only CI and test policy in `AGENTS.md`, restricting agents to Ruff, mypy, and pytest unit checks.
- Added repository-level `pytest.ini` to scope test discovery to `tests/unit` with quiet output and to avoid auto-loading unsupported plugins.
- Disabled the Docker-dependent integration probe by marking `tests/test_addon_installation.py` as skipped in environments without the Home Assistant runtime.
- Added `tests/unit/.gitkeep` to ensure the documented pytest target directory exists for discovery.

## Testing
- Not applicable (documentation of allowed commands only).
