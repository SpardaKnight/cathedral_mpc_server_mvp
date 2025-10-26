# Patch 0123 – s6 bootstrap alignment

## Summary
- Resolve Supervisor boot failure caused by `s6-overlay-suexec: fatal: can only run as pid 1` when the add-on attempted to launch via CMD.
- Move Cathedral Orchestrator startup into an s6 service at `/etc/services.d/cathedral/run` so `/init` stays PID 1 and executes `/opt/app/run.sh`.
- Provide a no-op `/etc/services.d/cathedral/finish` to satisfy s6 expectations and declare `init: false` in the manifest per s6 v3 requirements.
