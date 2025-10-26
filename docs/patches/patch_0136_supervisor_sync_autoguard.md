# Patch 0136 – Supervisor Sync Auto-Guard

## Summary
- Appended AGENTS.md ruleset enforcing Supervisor manifest alignment, s6 v3 service layout, and Dockerfile invariants.
- Added static pytest checks under `tests/static/` to enforce manifest version/init discipline and guard Dockerfile + service scripts.
- Goal: prevent merges that forget manifest bumps, `init: false`, or break runtime launch chain by hard-gating CI.
