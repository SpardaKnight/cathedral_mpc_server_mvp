# Cathedral Orchestrator (Home Assistant Add-on)

Cathedral Orchestrator bridges Home Assistant with Cathedral’s OpenAI-compatible relay and MPC tool stack. The add-on proxies Chat Completions and Embeddings to operator-supplied LM Studio hosts, exposes `/mcp` for Cathedral tools, and keeps vector state in Chroma (HTTP or embedded). All writes to `/data/sessions.db` and `/data/chroma` follow the single-writer rule.

- **MegaDoc**: [docs/MegaDoc.md](docs/MegaDoc.md) – complete architecture, schema, and operator guidance.
- **Smoke Build**: [docs/operations/smoke-build.md](docs/operations/smoke-build.md) – the only sanctioned validation path.

## Quick Install (Home Assistant Supervisor)
1. Open **Settings → Add-ons → Add-on Store → ⋮ → Repositories**.
2. Add `https://github.com/SpardaKnight/cathedral_mpc_server_mvp` (no `.git`).
3. Press **⋮ → Reload** so Supervisor indexes the repository.
4. Install **Cathedral Orchestrator** from the *Cathedral* section (or *Local add-ons* if you copied the repo into `/addons/cathedral_orchestrator`).
5. Configure options, save, and start the add-on. Hot updates can be applied later via `POST /api/options`, but persist through the UI to survive restarts.

## Configuration Snapshot
| Option | Type | Default | Description |
| --- | --- | --- | --- |
| `lm_hosts` | list(url) | `[]` | Base URLs for LM Studio/OpenAI-compatible hosts. Trailing `/v1` is removed automatically. |
| `chroma_mode` | `"http"` or `"embedded"` | `"http"` | Select remote Chroma or embedded persistence. |
| `chroma_url` | str? | `"http://127.0.0.1:8000"` | Required when `chroma_mode` is `"http"`. |
| `chroma_persist_dir` | str? | `"/data/chroma"` | Required when `chroma_mode` is `"embedded"`. |
| `collection_name` | str | `"cathedral"` | Chroma collection name. |
| `allowed_domains` | list(str) | `["light","switch","scene"]` | Home Assistant domains exposed to Cathedral tools. |
| `temperature` | float | `0.7` | Default sampling temperature forwarded to LM hosts. |
| `top_p` | float | `0.9` | Default nucleus sampling value. |
| `upserts_enabled` | bool | `true` | Enables vector upserts; disable for read-only mode.

Full schema and JSON example: [docs/schemas/ADDON_OPTIONS.md](docs/schemas/ADDON_OPTIONS.md).

Example `options` block:
```yaml
lm_hosts:
  - "http://192.168.1.233:1234"
chroma_mode: "http"
chroma_url: "http://192.168.1.42:8000"
chroma_persist_dir: "/data/chroma"
collection_name: "cathedral"
allowed_domains:
  - light
  - switch
  - scene
temperature: 0.7
top_p: 0.9
upserts_enabled: true
```

## Curl Taps
```bash
# Health probe: LM host counts + Chroma readiness
curl -s http://homeassistant.local:8001/health | jq

# Enumerate routed models
curl -s http://homeassistant.local:8001/v1/models | jq

# Embeddings relay example
curl -s http://homeassistant.local:8001/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "status check", "model": "text-embedding-3-large"}'
```

## Development Parity
For local work that matches the add-on image:
```bash
cd dev
./venv/activate.sh  # creates .venv with the same pins as /opt/venv
```

To mirror Supervisor’s build without running runtime tests:
```bash
make -C dev build_amd64
```

More details on build parity, security posture, concurrency, and operations live in [docs/](docs/__index__.md).
