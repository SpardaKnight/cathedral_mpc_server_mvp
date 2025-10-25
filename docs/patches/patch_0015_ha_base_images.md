# Patch 0015: Switch orchestrator add-on to Debian base images

## Summary
- update Home Assistant add-on build matrix to use `*-base-debian:bookworm` images
- align orchestrator Dockerfile with new base image, preserving venv setup and port 5005 exposure
- bump add-on version to 0.1.2 to trigger rebuild with new base

## Testing
- `pytest`
- `ruff check .`
- `mypy`
