# Cathedral Orchestrator Docs Changelog

## 0.1.3
- Document `/v1/models` metadata enrichment and the `/api/v0/models` aggregator so operators know context windows are surfaced
  automatically for AnythingLLM and similar clients.
- Capture the new runtime requirements manifest (with PyYAML) in the Docker build description to keep packaging steps aligned.

## 0.1.2
- Home Assistant add-on manifest mirrored in YAML/JSON with tcp watchdog, port descriptions, and version bump guidance for store updates.
- `/api/status` documented with readiness flags, catalog export, and per-host health telemetry.
- SSE relay contract reiterated with enforced `text/event-stream` and synthetic `[DONE]` frame handling.
- MPC scopes `resources.list`/`resources.health` highlighted alongside host assignment and Chroma collection persistence.
- `/api/options` locking notes updated so `chroma_mode` remains protected when `lock_VECTOR_DB` is enabled.

## 0.1.1
- Captured schema correction for `lm_hosts` (`list(url)`) and aligned YAML/JSON manifests.
- Documented migration to Debian Bookworm base image and `/opt/venv` install strategy.
- Recorded repository layout compliance with Home Assistant add-on requirements.
- Version bump references set to `0.1.1` for Supervisor builds.

## Unreleased
- Documented `/api/status` readiness payload (catalog, host health, sessions) and MPC host/model assignment.
- Recorded SSE relay hardening with enforced `text/event-stream`, idle timeouts, and synthetic `[DONE]` frames.
- Added `/api/options` hot-apply guardrails, per-key locks, and Chroma collection provisioning notes.

## Adopt EVE MegaDoc structure + HA env mirror
- Added Cathedral MegaDoc, structured schema/spec/ops docs, and source doclets mirroring the EVE Data Export discipline.
- Published HA Supervisor-style smoke build as the sole validation path.
- Introduced local Debian + venv parity scripts under `dev/` to match runtime expectations.
