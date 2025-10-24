#!/usr/bin/env python3
import sys, asyncio, websockets, json, uuid

BASE = sys.argv[1] if len(sys.argv)>1 else "ws://homeassistant.local:5005/mcp"

async def main():
    async with websockets.connect(BASE) as ws:
        rid = str(uuid.uuid4())
        await ws.send(json.dumps({"id":rid,"scope":"session.create","workspace_id":"ws1","conversation_id":"test"}))
        print(await ws.recv())

        rid2 = str(uuid.uuid4())
        await ws.send(json.dumps({"id":rid2,"scope":"tools.call","tool":"light.turn_on","payload":{"entity_id":"light.kitchen"}}))
        print(await ws.recv())

asyncio.run(main())
