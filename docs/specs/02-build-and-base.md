# Build and Base Specification

## Base Image
- **Source**: `ghcr.io/home-assistant/amd64-debian:bookworm`
- **Rationale**: Debian Bookworm provides glibc-compatible wheels for `onnxruntime`, `uvloop`, and other dependencies bundled with Chroma. Alpine/musl is unsupported.

## Virtual Environment
- Created at `/opt/venv` during Docker build using `python3 -m venv /opt/venv`.
- Pip upgraded before installing pinned packages: `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic`, `tiktoken`, `websockets`, `uvloop`, `httptools`, `aiosqlite`, `chromadb`.
- Application code copied into `/opt/app/orchestrator` and executed via `/opt/venv/bin/python`.

## Supervisor Build Flags
Supervisor invokes BuildKit with metadata labels so the resulting image is recognized as an add-on. These flags mirror `cathedral_orchestrator/build.json`.

```
docker buildx build . \
  --file cathedral_orchestrator/Dockerfile \
  --platform linux/amd64 \
  --pull \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-debian:bookworm \
  --label "io.hass.type=addon" \
  --label "io.hass.arch=amd64" \
  --label "io.hass.name=Cathedral Orchestrator" \
  --label "io.hass.version=0.1.1"
```

## Build Outputs
- The resulting image ships `/opt/venv` and `/opt/app/orchestrator` only. Supervisor mounts `/data` for runtime state.
- No extra package managers (apt) remain in the final layer beyond what the base image provides.
- The entrypoint is `bashio`-driven `run.sh`, which activates `/opt/venv/bin/python`.

Operators must use the same build flags locally to reproduce Supervisor behavior. No additional tests are run during the build.
