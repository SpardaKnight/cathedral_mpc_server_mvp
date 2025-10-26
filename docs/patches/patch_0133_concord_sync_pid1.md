# Patch 0133 — Concord Sync & s6 PID1 Hardening

This patch reconciles manifest, runtime scripts, and documentation with the actual s6 v3 launch path so Supervisor builds stay deterministic.

- Bumped add-on version to 1.1.8 and reaffirmed `init: false` with no `host_pid` override.
- Locked Dockerfile header to `ARG BUILD_FROM` / `FROM $BUILD_FROM` with chmod-only adjustments and no custom CMD/ENTRYPOINT.
- Normalized the s6 service chain: execlineb `run`, halt-aware `finish`, and `/opt/app/start.sh` probing LM/Chroma before `exec uvicorn`.
- Enforced executable bits via git metadata and added `.gitattributes` guards to keep LF line endings.
- Updated README, AGENTS, and changelog docs so operators see the exact startup order and PID 1 expectations.
