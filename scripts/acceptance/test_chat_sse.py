#!/usr/bin/env python3
import sys, httpx, asyncio

BASE = sys.argv[1] if len(sys.argv)>1 else "http://homeassistant.local:8001"

async def main():
    payload = {
        "model": "openai/gpt-oss-20b",
        "stream": True,
        "messages": [{"role":"user","content":"Say hello from Cathedral"}]
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{BASE}/v1/chat/completions", json=payload) as r:
            async for chunk in r.aiter_text():
                print(chunk, end="")
                if "data: [DONE]" in chunk:
                    break

if __name__ == "__main__":
    asyncio.run(main())
