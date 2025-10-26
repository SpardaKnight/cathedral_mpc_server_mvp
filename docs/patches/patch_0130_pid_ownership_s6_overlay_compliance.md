# Patch 0130 — PID Ownership & s6-overlay Compliance

This patch resolves a fatal startup conflict where both run.sh and the s6 supervisor attempted to launch the orchestrator, violating the PID 1 model. This caused: `s6-overlay-suexec: fatal: can only run as pid 1`.

- Removed run.sh from top-level add-on structure
- Migrated all startup logic under `rootfs/etc/services.d/cathedral/`, letting s6 manage uvicorn as PID 1
- LM and Chroma preflight probes now occur before uvicorn launch
- Uvicorn is now executed as the PID 1 foreground process
- config.yaml version bumped to 1.1.6
