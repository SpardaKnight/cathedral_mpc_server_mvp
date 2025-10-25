Cathedral Orchestrator (Home Assistant add-on)

OpenAI-compatible relay and MPC WebSocket server that runs inside Home Assistant and routes all LLM work to LM Studio on your Windows GPU box. Semantic memory is persisted to Chroma (either an external Chroma server on Windows or an embedded store inside the add-on).

GPU work (chat + embeddings) happens on your 5090 via LM Studio.

Chroma stores vectors on CPU and can run externally (recommended) or embedded in the add-on.

What you get

/v1/models, /v1/chat/completions (SSE), /v1/embeddings — OpenAI-compatible endpoints proxied to LM Studio

/mcp WebSocket — MPC server for session.*, memory.*, config.*, prompts.*, sampling.*, resources.*, agents.*; tools.* are delegated to HA’s LLM API

SQLite sessions stored in /data/sessions.db with aiosqlite + WAL

Chroma client (dual-mode)

http → talk to a Chroma HTTP server (Windows 5090 or HA)

embedded → persist vectors inside the add-on under /data/chroma

Single-writer switch for vectors (upserts_enabled) so either the Orchestrator or AnythingLLM writes to Chroma (not both)

Requirements

Home Assistant OS with Supervisor

Windows 11 GPU machine (your 5090) running LM Studio

Optional: Chroma server on the 5090 (external mode). Otherwise use embedded mode.

Network:

Home Assistant must reach LM Studio (e.g. http://<5090-IP>:1234)

If using external Chroma, HA must reach http://<CHROMA-HOST>:8000

Quick install

Add the add-on repository
Settings → Add-ons → Add-on Store → ⋮ → Repositories → add:

https://github.com/SpardaKnight/cathedral_mpc_server_mvp


Install the add-on
Find Cathedral Orchestrator → Install → Configure (next section) → Start.

Configure options (Add-on → Configuration)

lm_hosts: {"primary": "http://<5090-IP>:1234"}  # LM Studio base URL (no /v1)
chroma_mode: "http"                              # "http" or "embedded"
chroma_url: "http://<host>:8000"                 # only used in http mode
chroma_persist_dir: "/data/chroma"               # used in embedded mode
collection_name: "cathedral"
allowed_domains: ["light","switch","scene"]
temperature: 0.7
top_p: 0.9
upserts_enabled: true                            # orchestrator writes vectors


Single-writer rule
If you want AnythingLLM to be the only writer to Chroma, set upserts_enabled: false here to avoid duplicates.

Start the add-on and confirm the logs show LM Studio models and Chroma health.

Set up the Windows 5090 node
LM Studio (GPU)

Install LM Studio and start its local API. Example base URL: http://<5090-IP>:1234

Load your chat and embedding models.

The add-on uses /v1/chat/completions and /v1/embeddings, so embeddings always run on your GPU.

Chroma (external mode, recommended)

PowerShell (Admin):

pip install chromadb
$env:CHROMA_PORT=8000
$env:CHROMA_PATH="D:\ChromaDB"
chroma run --host 0.0.0.0 --port $env:CHROMA_PORT --path $env:CHROMA_PATH


Optional Windows firewall (LAN only):

New-NetFirewallRule -DisplayName "Chroma 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow


Add-on options:

chroma_mode: "http"
chroma_url: "http://<5090-IP>:8000"

Chroma (embedded mode)

If you prefer simplicity:

chroma_mode: "embedded"
chroma_persist_dir: "/data/chroma"


Vectors are stored inside the add-on under /data/chroma.

AnythingLLM wiring (optional)

If you’re using AnythingLLM alongside the Orchestrator:

LLM Provider: LM Studio — Base http://<5090-IP>:1234/v1

Embedder: LM Studio — Base http://<5090-IP>:1234/v1/embeddings

Vector DB: Chroma — Endpoint http://<host>:8000 (your 5090 or HA)

MPC (optional): ws://<HA-IP>:5005/mcp

If A-LLM writes to Chroma directly, keep upserts_enabled: false in the add-on.

Validate the deployment
# Orchestrator health
curl -s http://<HA-IP>:8001/health | jq

# LM Studio reachable through relay
curl -s http://<HA-IP>:8001/v1/models | jq

# Simple non-stream chat
curl -s http://<HA-IP>:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<chat-model-id>","stream":false,"messages":[{"role":"user","content":"ping"}]}'

# Embeddings (and upsert if enabled)
curl -s http://<HA-IP>:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"<embed-model-id>","input":"hello vector db","metadata":{"workspace_id":"ws_demo","role":"user"}}'


External Chroma health:

curl -s http://<CHROMA-HOST>:8000/docs | head -n 1

How it works

Relay: /v1/models, /v1/chat/completions, /v1/embeddings forward to LM Studio.
Chat is streamed via SSE and closes with data: [DONE].

Embeddings: always computed by LM Studio on your GPU.
If upserts_enabled: true, vectors are then written to Chroma with metadata.

Chroma:

http mode uses chromadb.HttpClient(host, port)

embedded mode uses chromadb.Client(Settings(persist_directory="/data/chroma", is_persistent=True))

Sessions: stored under /data/sessions.db via aiosqlite + WAL.

MPC: WebSocket at /mcp for session.*, memory.*, config.*, prompts.*, sampling.*, resources.*, agents.*.
tools.* actions are delegated to HA’s LLM API and allow-listed domains.

Common choices and modes
Choice	Set this	When to use
External Chroma (recommended)	chroma_mode: "http", chroma_url: "http://<5090-IP>:8000"	Best for larger datasets; vectors live with your GPU host
Embedded Chroma	chroma_mode: "embedded", chroma_persist_dir: "/data/chroma"	Simpler; good for moderate size
Orchestrator writes vectors	upserts_enabled: true	Centralize memory writes in Orchestrator
A-LLM writes vectors	upserts_enabled: false	Keep RAG inside AnythingLLM
Troubleshooting

/v1/models fails: lm_hosts must be the base of LM Studio (no /v1). Check Windows firewall.

SSE chat cuts off: this build sets read=None on the upstream timeout; also check any reverse proxies.

Chroma unreachable: in external mode use the host LAN IP, not 127.0.0.1. /docs should return 200.

Duplicate vectors: ensure only one writer. If A-LLM writes, set upserts_enabled: false.

No GPU use: LM Studio must have both chat and embedding models running.

Security notes

The add-on uses the Supervisor token to talk to HA; no LLATs are needed.

Keep HA ports 8001 and 5005 LAN-only unless you front them with an auth-enforcing reverse proxy.

Keep Chroma LAN-only; if exposed, protect with a reverse proxy that adds an auth header.

Uninstall / upgrade

Stop and remove the add-on in HA.

Embedded vectors live under /data/chroma (back up if needed).

External vectors live in your Chroma --path directory (e.g., D:\ChromaDB).

Maintainers

Add-on: addons/cathedral_orchestrator/

Endpoints: /v1/*, /mcp, /api/*

Config source: /data/options.json (Supervisor writes), hot-apply via POST /api/options
