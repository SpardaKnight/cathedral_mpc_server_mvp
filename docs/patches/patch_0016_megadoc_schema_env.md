# Patch 0016 — MegaDoc, Schema Reference, and HA Env Mirror

## Summary
- Added Cathedral MegaDoc, structured specs, schema, and operations docs aligned with the EVE Data Export discipline.
- Rewrote README with install guidance, schema snapshot, curl taps, and documentation links.
- Introduced `dev/` parity tools (venv script and Makefile) and documented the Supervisor-style smoke build.

## Validation
- No automated tests executed per Concord; validation is the documented Docker `buildx` smoke command mirroring Supervisor.
