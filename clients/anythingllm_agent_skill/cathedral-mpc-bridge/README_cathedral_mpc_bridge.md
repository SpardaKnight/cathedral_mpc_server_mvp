# Cathedral MPC Bridge — AnythingLLM Agent Skill (Desktop)

## Install (Windows)
1) Open Desktop storage:
   C:\Users\<YOU>\AppData\Roaming\anythingllm-desktop\storage
2) Create folder:
   plugins\agent-skills\cathedral-mpc-bridge
3) Copy from repo:
   plugin.json, handler.js
4) Edit handler.js and set:
   const AUTH = "Bearer <YOUR_LONG_LIVED_TOKEN_HERE>";
5) In AnythingLLM → Agent Skills → enable "Cathedral MPC Bridge".
6) The bridge auto-connects to: ws://homeassistant.local:5005/mcp

## Verify
- AnythingLLM logs: [Cathedral-MPC-Bridge][info] Connected to ws://homeassistant.local:5005/mcp
- HA logs: handshake then config.read.result
- GET http://homeassistant.local:8001/v1/models returns LM Studio models (union)

## Notes
- This folder is for the AnythingLLM Desktop plugin only.
- It is separate from the Home Assistant add-on under addons/cathedral_orchestrator/.
