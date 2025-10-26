#!/usr/bin/env bash
set -euo pipefail
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install fastapi==0.115.0 uvicorn==0.30.6 httpx==0.27.2 pydantic==2.9.2 \
            tiktoken==0.7.0 websockets==12.0 uvloop==0.19.0 httptools==0.6.1 \
            aiosqlite==0.20.0
echo "Dev venv mirrors add-on /opt/venv."
