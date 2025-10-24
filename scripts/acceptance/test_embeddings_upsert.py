#!/usr/bin/env python3
import sys, httpx, json, uuid
BASE = sys.argv[1] if len(sys.argv)>1 else "http://homeassistant.local:8001"
text = "Vector test " + str(uuid.uuid4())
payload = {"model":"bge-m3","input":[text],"metadata":{"thread_id":"local-test"}}
r = httpx.post(f"{BASE}/v1/embeddings", json=payload, timeout=60)
print(r.status_code, r.text)
