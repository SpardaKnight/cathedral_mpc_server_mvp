#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-http://homeassistant.local:8001}
curl -sS -X POST "$BASE/api/options" -H "Content-Type: application/json" -d '{"temperature":0.5,"top_p":0.8}' | jq .
curl -sS "$BASE/api/status" | jq .
