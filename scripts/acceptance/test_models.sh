#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-http://homeassistant.local:8001}
curl -sS ${BASE}/v1/models | jq .
