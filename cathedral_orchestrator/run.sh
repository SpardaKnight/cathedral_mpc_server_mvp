#!/usr/bin/env bash
set -euo pipefail

OPTS="/data/options.json"
[ -f "$OPTS" ] || { echo "[FATAL] Missing /data/options.json" >&2; exit 1; }

# Support lm_hosts as list(url) or dict -> enumerate values
LM_HOSTS="$(jq -r '
  .lm_hosts
  | if type=="array" then .[]
    elif type=="object" then to_entries[] | .value
    elif type=="string" then .
    else empty end
' "$OPTS")"

CHROMA_MODE="$(jq -r '.chroma_mode' "$OPTS")"
CHROMA_URL="$(jq -r '.chroma_url // empty' "$OPTS")"

echo "[INFO] Preflight: LM Studio models"
for host in $LM_HOSTS; do
  echo "  -> $host/v1/models"
  curl -fsS "$host/v1/models" >/dev/null || echo "[WARN] LM Studio not reachable: $host"
done

if [ "$CHROMA_MODE" = "http" ] && [ -n "${CHROMA_URL:-}" ]; then
  echo "[INFO] Preflight: Chroma /docs"
  curl -fsS "$CHROMA_URL/docs" >/dev/null || echo "[WARN] Chroma not reachable: $CHROMA_URL"
fi

CPU=$(getconf _NPROCESSORS_ONLN || echo 2)
WORKERS=$(( CPU * 2 ))

echo "[INFO] Starting Uvicorn on 0.0.0.0:8001 with $WORKERS workers"
uvicorn orchestrator.main:app \
  --host 0.0.0.0 --port 8001 \
  --loop auto \
  --workers "${WORKERS}" &

echo "[INFO] Starting Uvicorn on 0.0.0.0:5005 with $WORKERS workers (MPC WS)"
exec uvicorn orchestrator.main:app \
  --host 0.0.0.0 --port 5005 \
  --loop auto \
  --workers "${WORKERS}"
