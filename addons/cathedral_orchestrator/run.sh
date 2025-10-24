#!/usr/bin/with-contenv bashio
# Preflight: parse /data/options.json and check LM Studio & Chroma health before starting

set -euo pipefail

OPTIONS_FILE="/data/options.json"
if [ ! -f "$OPTIONS_FILE" ]; then
  echo "[FATAL] Missing /data/options.json" >&2
  exit 1
fi

LM_HOSTS=$(jq -r '.lm_hosts | to_entries[] | .value' "$OPTIONS_FILE")
CHROMA_MODE=$(jq -r '.chroma_mode' "$OPTIONS_FILE")
CHROMA_URL=$(jq -r '.chroma_url' "$OPTIONS_FILE")

echo "[INFO] Preflight: LM Studio model lists"
for host in $LM_HOSTS; do
  echo "  - Checking $host/v1/models"
  if ! curl -sf "$host/v1/models" > /dev/null; then
    echo "[WARN] LM Studio host unreachable: $host"
  fi
done

if [ "$CHROMA_MODE" = "http" ]; then
  echo "[INFO] Preflight: Chroma $CHROMA_URL/docs"
  if ! curl -sf "$CHROMA_URL/docs" > /dev/null; then
    echo "[WARN] Chroma server unreachable at $CHROMA_URL (HTTP mode)"
  fi
fi

echo "[INFO] Starting Uvicorn on 0.0.0.0:8001"
exec uvicorn orchestrator.main:app --host 0.0.0.0 --port 8001
