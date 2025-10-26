# Patch 0131 — s6-overlay PID Fix (Final)

This patch eliminates all residual entrypoints and restores proper PID 1 behavior under s6-overlay. Fully deletes run.sh, removes CMD/ENTRYPOINT from Dockerfile, validates s6 service file, and confirms LM/Chroma preflight logic.
