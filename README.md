# Cathedral Orchestrator (Home Assistant Add-on)

Cathedral Orchestrator is a Home Assistant (HA) **Supervisor add-on** that exposes:
- **OpenAI-compatible HTTP endpoints** (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`) to relay requests to **LM Studio** on your Windows GPU host.
- An **MPC WebSocket server** at `/mcp` for session/config/memory coordination, delegating `tools.*` actions to Home Assistant’s LLM API.

**Embeddings and chat generation are always performed by LM Studio on your GPU**. The orchestrator never embeds locally. Vector storage is handled by **Chroma** using one of two modes:
- **HTTP mode**: the add-on connects to an external Chroma server (recommended; run it on your 5090 or another host).
- **Embedded mode**: the add-on uses an embedded Chroma client that persists under `/data/chroma` inside the add-on.

A **single‑writer switch** (`upserts_enabled`) ensures only one system writes vectors to Chroma (Orchestrator or AnythingLLM).

---

## Contents
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Install in Home Assistant](#install-in-home-assistant)
  - [Option A — Local Add-on (private repo)](#option-a--local-add-on-private-repo)
  - [Option B — Add-on Store Repository (public repos only)](#option-b--add-on-store-repository-public-repos-only)
  - [Configure the add-on](#configure-the-add-on)
  - [Start and validate](#start-and-validate)
- [Set up the Windows 5090 node](#set-up-the-windows-5090-node)
  - [LM Studio (GPU)](#lm-studio-gpu)
  - [Chroma (HTTP server)](#chroma-http-server)
- [AnythingLLM wiring (optional)](#anythingllm-wiring-optional)
- [Modes and recommended choices](#modes-and-recommended-choices)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)

---

## Architecture

```
AnythingLLM (Windows)
 ├─ HTTP → HA Orchestrator /v1/*        # OpenAI-compatible relay to LM Studio
 └─ WS  → HA Orchestrator /mcp          # MPC (session/config/memory), tools delegated to HA

Home Assistant Add-on: Cathedral Orchestrator
 ├─ /v1/models | /v1/chat/completions | /v1/embeddings → LM Studio
 ├─ Writes to Chroma (if upserts_enabled: true)
 ├─ WS /mcp (session.*, memory.*, config.*, prompts.*, sampling.*, resources.*, agents.*)
 └─ SQLite sessions at /data/sessions.db (aiosqlite + WAL)

Windows 5090 (GPU)
 ├─ LM Studio (OpenAI-compatible API on http://<5090-IP>:1234/v1)
 └─ Optional: Chroma HTTP server (default :8000)
```

**Key points**
- LM Studio performs all GPU work (chat + embeddings).
- Chroma is CPU-only and stores vectors. Use HTTP mode for best performance, or embedded mode for simplicity.
- Only one system should write vectors to Chroma to prevent duplicates (`upserts_enabled` flag in the add-on).

---

## Requirements

- **Home Assistant OS** with **Supervisor** (Add-ons capability)
- A **Windows 11** machine with a **GPU** (e.g., 5090) running **LM Studio**
- Optional but recommended: a **Chroma HTTP server** (can run on the 5090)

Network:
- HA must reach LM Studio on its base URL (e.g., `http://<5090-IP>:1234`).
- If you use external Chroma, HA must reach `http://<CHROMA-HOST>:8000`.

---

## Install in Home Assistant

> Because this repository is private, the most reliable approach is a **Local Add-on** install (Option A).

### Option A — Local Add-on (private repo)

1. Install either **Studio Code Server** or **Samba Share** add-on in HA (to edit files under `/addons`).  
2. Create a folder on your HA host (case sensitive):
   ```
   /addons/cathedral_orchestrator/
   ```
3. Copy the add-on content from this repository into that folder. The structure must include at minimum:
   ```
   addons/cathedral_orchestrator/
     ├─ config.yaml
     ├─ Dockerfile
     ├─ run.sh
     └─ orchestrator/
         ├─ main.py
         ├─ mpc_server.py
         ├─ toolbridge.py
         ├─ sse.py
         ├─ logging_config.py
         ├─ sessions.py
         └─ vector/
             └─ chroma_client.py
   ```
4. Go to **Settings → Add-ons → Add-on Store**. There should be a **Local add-ons** section showing **Cathedral Orchestrator**.

### Option B — Add-on Store Repository (public repos only)

If the repo is made public, you can add it as a repository:
1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Add repository URL:
   ```
   https://github.com/SpardaKnight/cathedral_mpc_server_mvp
   ```
3. Install **Cathedral Orchestrator** from the store.

> For private repos, HA cannot access the code directly from GitHub. Use Option A.

### Configure the add-on

Open the add-on **Configuration** tab and set the options. Minimal working config:

```yaml
lm_hosts: {"primary": "http://<5090-IP>:1234"}  # LM Studio base URL (no /v1)
chroma_mode: "http"                              # "http" or "embedded"
chroma_url: "http://<host>:8000"                 # used only in http mode
chroma_persist_dir: "/data/chroma"               # used only in embedded mode
collection_name: "cathedral"
allowed_domains: ["light","switch","scene"]
temperature: 0.7
top_p: 0.9
upserts_enabled: true                            # orchestrator writes vectors
```

**Single-writer rule**  
If **AnythingLLM** writes vectors directly to Chroma, set `upserts_enabled: false` here to avoid duplicate inserts.

### Start and validate

1. Click **Start** on the add-on.  
2. Check logs for:
   - LM Studio model enumeration success
   - Chroma health (HTTP mode) or embedded init
3. From any LAN machine, verify:
   ```bash
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
   ```
   If using external Chroma:
   ```bash
   curl -s http://<CHROMA-HOST>:8000/docs | head -n 1
   ```

---

## Set up the Windows 5090 node

### LM Studio (GPU)

1. Install LM Studio and start its local API. Example: `http://<5090-IP>:1234`
2. Load your **chat** model (for `/v1/chat/completions`) and **embedding** model (for `/v1/embeddings`).  
3. Ensure Windows firewall allows inbound connections on the LM Studio port.

### Chroma (HTTP server)

External mode is recommended for larger datasets and clean separation from HA.

PowerShell (Administrator):
```powershell
pip install chromadb
$env:CHROMA_PORT=8000
$env:CHROMA_PATH="D:\ChromaDB"
chroma run --host 0.0.0.0 --port $env:CHROMA_PORT --path $env:CHROMA_PATH
```

Optional Windows firewall (LAN only):
```powershell
New-NetFirewallRule -DisplayName "Chroma 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

Add-on options for external Chroma:
```yaml
chroma_mode: "http"
chroma_url: "http://<5090-IP>:8000"
```

**Embedded mode** (simple start, smaller datasets):
```yaml
chroma_mode: "embedded"
chroma_persist_dir: "/data/chroma"
```

---

## AnythingLLM wiring (optional)

If you are using AnythingLLM alongside the Orchestrator:

- **LLM Provider**: LM Studio — Base `http://<5090-IP>:1234/v1`
- **Embedder**: LM Studio — Base `http://<5090-IP>:1234/v1/embeddings`
- **Vector DB**: Chroma — Endpoint `http://<host>:8000` (5090 or HA)
- **MPC (optional)**: `ws://<HA-IP>:5005/mcp`

**Important:** If A‑LLM writes vectors to Chroma, set the add-on `upserts_enabled: false` so the Orchestrator does not also write.

---

## Modes and recommended choices

| Scenario | Setting | Why |
|---|---|---|
| Production‑like | `chroma_mode: "http"`, `chroma_url: "http://<5090-IP>:8000"` | Best performance; vectors live with your GPU host |
| Simple start | `chroma_mode: "embedded"`, `chroma_persist_dir: "/data/chroma"` | Fewer moving parts; ideal for small to medium data |
| Orchestrator is vector owner | `upserts_enabled: true` | Centralizes memory policy in one place |
| AnythingLLM is vector owner | `upserts_enabled: false` | Keeps RAG fully inside A‑LLM |

---

## Troubleshooting

- **/v1/models fails**: `lm_hosts` must be the **base** of LM Studio (no `/v1`). Confirm Windows firewall rules.
- **SSE stream cuts off**: This build sets streaming `read=None`; if you front HA with a proxy, increase its read timeout.
- **Chroma unreachable**: In HTTP mode use the host LAN IP, not `127.0.0.1`. `/docs` should return 200.
- **Duplicate vectors**: Ensure only one writer. If A‑LLM writes, set `upserts_enabled: false`.
- **Slow replies**: All GPU work is in LM Studio. Verify the selected model and GPU utilization there.

---

## Security Notes

- The add-on uses the Supervisor token (`hassio_api: true`) to talk to HA; do not expose that value.  
- Keep Orchestrator ports (8001, 5005) **LAN‑only**, or protect with an authenticating reverse proxy if you must expose.  
- Keep Chroma LAN‑only. If exposed, front it with a reverse proxy enforcing auth headers/tokens.

---

## Maintainers & Structure

- Add-on root: `addons/cathedral_orchestrator/`  
  - `config.yaml`, `Dockerfile`, `run.sh`  
  - `orchestrator/` (`main.py`, `mpc_server.py`, `sessions.py`, `vector/chroma_client.py`, etc.)

**Config source**: HA Supervisor writes `/data/options.json` inside the add-on; runtime changes can be hot‑applied through `POST /api/options`.
