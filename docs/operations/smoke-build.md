# Supervisor-style Smoke Build

The Cathedral Orchestrator add-on forbids synthetic unit tests. The sole validation is replicating Home Assistant Supervisor’s Docker build using the same base image, build args, and metadata labels.

## Prerequisites
- Docker with BuildKit and `buildx` support.
- Network access to `ghcr.io` to pull `ghcr.io/home-assistant/amd64-debian:bookworm`.

## Command
Run from the repository root:

```bash
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

## Expectations
- Successful completion proves the Docker context, dependencies, and pinned wheels mirror the Supervisor build path.
- The command does **not** run the container or execute integration tests; it only validates build reproducibility.
- If the build fails, do not attempt to patch around it with mocks—fix the Dockerfile or dependency pins and rerun the smoke build.
