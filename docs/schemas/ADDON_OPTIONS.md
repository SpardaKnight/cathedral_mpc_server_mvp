# Cathedral Orchestrator Add-on Options

The options below are authoritative for `cathedral_orchestrator/config.yaml` and `config.json`. The schema mirrors Home Assistant Supervisor semantics so hot-apply payloads sent to `/api/options` stay compatible with stored add-on configuration.

| Option | Type | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `lm_hosts` | list(url) | Yes | `[]` | Ordered list of language model base URLs. Trailing `/v1` is stripped automatically, and chat completions continue streaming via the dedicated relay that now enters `client.stream(...)` as an async context. | `["http://192.168.1.233:1234"]` |
| `chroma_mode` | str (`"http"`) | Yes | `"http"` | HTTP mode only. Embedded mode has been removed; values other than `"http"` are coerced back to HTTP. | `"http"` |
| `chroma_url` | str? | Conditional | `"http://127.0.0.1:8000"` | Remote Chroma endpoint used when `chroma_mode` is `"http"`. Ignored for embedded mode. | `"http://192.168.1.42:8000"` |
| `chroma_persist_dir` | str? | Optional | `"/data/chroma"` | Legacy option retained for schema compatibility. Ignored by the HTTP-only client. | `"/data/chroma"` |
| `collection_name` | str | Yes | `"cathedral"` | Chroma collection that stores embeddings for the orchestrator. | `"cathedral"` |
| `allowed_domains` | list(str) | Yes | `["light","switch","scene"]` | Home Assistant domains exposed to MPC tools. | `["light","switch","scene","media_player"]` |
| `temperature` | float | Yes | `0.7` | Default sampling temperature applied to LM Studio compatible hosts. | `0.6` |
| `top_p` | float | Yes | `0.9` | Default nucleus sampling value passed through to upstream models. | `0.85` |
| `upserts_enabled` | bool | Yes | `true` | Enables real-time embedding upserts to Chroma. Disable to operate in read-only replay mode. | `false` |
| `auto_config` | bool | Yes | `true` | Enables Supervisor-managed bootstrap for LM hosts and reflects in `/api/status`. | `true` |
| `auto_discovery` | bool | Yes | `false` | Reserved toggle for LAN discovery of LM hosts. Currently no-op but persisted for parity. | `false` |
| `lock_hosts` | bool | Yes | `false` | Prevents remote config writes from altering `lm_hosts`. | `false` |
| `lock_LMSTUDIO_BASE_PATH` | bool | Yes | `false` | Locks MPC client override for LM Studio base path. | `false` |
| `lock_EMBEDDING_BASE_PATH` | bool | Yes | `false` | Locks MPC client override for embedding base path. | `false` |
| `lock_CHROMA_URL` | bool | Yes | `false` | Locks MPC client override for Chroma URL. | `false` |
| `lock_VECTOR_DB` | bool | Yes | `false` | Locks MPC client override for vector database selection. | `false` |

## Hot-apply example payload

```json
{
  "lm_hosts": ["http://192.168.1.233:1234"],
  "chroma_mode": "http",
  "chroma_url": "http://192.168.1.42:8000",
  "chroma_persist_dir": "/data/chroma",
  "collection_name": "cathedral",
  "allowed_domains": ["light", "switch", "scene"],
  "temperature": 0.7,
  "top_p": 0.9,
  "upserts_enabled": true,
  "auto_config": true,
  "auto_discovery": false,
  "lock_hosts": false,
  "lock_LMSTUDIO_BASE_PATH": false,
  "lock_EMBEDDING_BASE_PATH": false,
  "lock_CHROMA_URL": false,
  "lock_VECTOR_DB": false
}
```

Apply via `POST /api/options` to hot-load the configuration; persist the same structure back to Home Assistant Supervisor to survive restarts.
