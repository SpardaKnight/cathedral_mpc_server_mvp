# Cathedral Orchestrator Docs Changelog

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
