# Cathedral Orchestrator Docs Changelog

## 0.2.11
- Document `/debug/probe` for on-demand LM host diagnostics and enumerate the per-host exception metadata it returns.
- Capture the isolated HTTPX client strategy so operators know timeouts on one host no longer poison the pool for others.

## 0.2.6
- Document the non-blocking s6 startup probe flow and background bootstrap loop so operators know the API will come up even when LM hosts are offline.
- Capture the immediate `/api/options` refresh semantics and tightened LM client timeouts to guide troubleshooting for hostpool updates.

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

## Adopt EVE MegaDoc structure + HA env mirror
- Added Cathedral MegaDoc, structured schema/spec/ops docs, and source doclets mirroring the EVE Data Export discipline.
- Published HA Supervisor-style smoke build as the sole validation path.
- Introduced local Debian + venv parity scripts under `dev/` to match runtime expectations.
