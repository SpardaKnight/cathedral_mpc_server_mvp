#!/usr/bin/env bash
set -euo pipefail

OPTS="/data/options.json"
if [ ! -f "$OPTS" ]; then
  echo "[FATAL] Missing $OPTS" >&2
  exit 1
fi

LM_HOSTS=$(jq -r '
  .lm_hosts
  | if type=="array" then .[]
    elif type=="object" then to_entries[] | .value
    elif type=="string" then .
    else empty end
' "$OPTS")

CHROMA_URL=$(jq -r '.chroma_url // empty' "$OPTS")

ATTEMPTS=0
MAX_ATTEMPTS=60

for HOST in $LM_HOSTS; do
  TARGET="${HOST%/}/v1/models"
  echo "[WAIT] Probing LM host $TARGET"
  until curl -sS --fail "$TARGET" >/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
      echo "[FATAL] Timeout waiting for LM host $TARGET" >&2
      exit 1
    fi
    sleep 1
  done
  echo "[READY] LM host $TARGET responded"
done

if [ -n "${CHROMA_URL:-}" ]; then
  DOCS="${CHROMA_URL%/}/docs"
  echo "[WAIT] Probing Chroma docs at $DOCS"
  until curl -sS --fail "$DOCS" >/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
      echo "[FATAL] Timeout waiting for Chroma docs at $DOCS" >&2
      exit 1
    fi
    sleep 1
  done
  echo "[READY] Chroma docs available at $DOCS"
fi

echo "[INFO] Launching Cathedral Orchestrator"
exec uvicorn orchestrator.main:app --host 0.0.0.0 --port 8001
