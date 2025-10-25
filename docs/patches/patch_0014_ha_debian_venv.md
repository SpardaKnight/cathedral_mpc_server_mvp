# Patch 0014: Home Assistant addon Debian base + venv rebuild

## Summary
- switch addon base images to Debian bookworm variants for all arches
- rebuild Dockerfile to use apt packages and manage Python deps in /opt/venv
- restrict addon arch list to amd64 and bump version to 0.1.1 for Supervisor rebuild

## Testing
- not run (per instructions)
