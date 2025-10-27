#!/command/with-contenv bash
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

for HOST in $LM_HOSTS; do
  TARGET="${HOST%/}/v1/models"
  echo "[WAIT] Probing LM host $TARGET"
  until curl -sS --fail "$TARGET" >/dev/null; do
    echo "[ERROR] LM host not reachable: $TARGET" >&2
    sleep 2
  done
  echo "[READY] LM host $TARGET responded"
done

if [ -n "${CHROMA_URL:-}" ]; then
  DOCS="${CHROMA_URL%/}/docs"
  echo "[WAIT] Probing Chroma docs at $DOCS"
  until curl -sS --fail "$DOCS" >/dev/null; do
    echo "[ERROR] Chroma not reachable: $DOCS" >&2
    sleep 2
  done
  echo "[READY] Chroma docs available at $DOCS"
fi

cd /opt/app
export PYTHONPATH="/opt/app:${PYTHONPATH:-}"

echo "[INFO] Launching Cathedral Orchestrator"
uvicorn --app-dir /opt/app orchestrator.main:app --host 0.0.0.0 --port 8001 &
SERVER_PID=$!

for i in $(seq 1 60); do
  if nc -z 127.0.0.1 8001; then
    echo "[READY] Cathedral Orchestrator is listening on 8001"
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    wait "$SERVER_PID"
    exit 1
  fi
  sleep 1
done

if ! nc -z 127.0.0.1 8001; then
  echo "[ERROR] Cathedral Orchestrator did not open port 8001 within 60 seconds" >&2
  wait "$SERVER_PID"
  exit 1
fi

wait "$SERVER_PID"
