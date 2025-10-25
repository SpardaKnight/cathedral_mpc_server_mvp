# Patch 0011: Docker venv build compliance

- Switched the add-on Docker image build to create a Python virtual environment under `/opt/venv` and install the existing runtime dependencies there to satisfy PEP 668.
- Exported the virtual environment `PATH` so the existing `run.sh` entrypoint continues to locate `uvicorn` without modifications.
- Added a default `BUILD_FROM` argument pointing to `ghcr.io/home-assistant/amd64-base:3.19` to silence buildx warnings while preserving override capability.
- No application code or entrypoint scripts were modified, and per instructions no tests or CI pipelines were executed.
