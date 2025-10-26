# Patch 0132 — s6 PID Fix: Shell Script Externalization

This patch eliminates all inline shell execution logic from the service run file and moves it into a clean external script.

- Introduces /opt/app/start.sh with full LM + Chroma preflight logic and final uvicorn launch
- Service run file now simply execs that script under s6-overlay
- Version bumped to 1.1.7
- Resolves s6-overlay PID 1 conflict
