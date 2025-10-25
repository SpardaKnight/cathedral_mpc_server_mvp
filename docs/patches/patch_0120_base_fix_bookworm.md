# Patch 0120 — Fix base image 403 and lock Debian Bookworm
- Map build.json to ghcr.io/home-assistant/*-base-debian:bookworm
- Keep Dockerfile `FROM $BUILD_FROM` only; no hardcoded base lines
- Ensure dev/Makefile passes BUILD_FROM for local smoke
- Rationale: avoid 403 from deprecated/unauthorized tags and keep parity with Supervisor
