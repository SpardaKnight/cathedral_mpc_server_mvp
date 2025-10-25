# Patch 0010 — HA schema compliance for `lm_hosts` and WIP banner

- Normalize the Home Assistant add-on schema for `lm_hosts` to use `list(url)` with array defaults in `config.yaml` and `config.json`.
- Add `_normalize_lm_hosts()` in the orchestrator to accept dict/list/str inputs so existing options continue to work when hot-applied.
- Mark the repository as Work In Progress in `README.md`, `RUNBOOK.md`, and add `STATUS.md` for quick reference.
