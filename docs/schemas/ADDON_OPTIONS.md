# Cathedral Orchestrator Add-on Options

The options below are authoritative for `cathedral_orchestrator/config.yaml` and `config.json`. The schema mirrors Home Assistant Supervisor semantics so hot-apply payloads sent to `/api/options` stay compatible with stored add-on configuration.

| Option | Type | Required? | Default | Description | Example |
| --- | --- | --- | --- | --- | --- |
| `lm_hosts` | list(url) | Yes | `[]` | Ordered list of language model base URLs. Trailing `/v1` is stripped automatically. | `["http://192.168.1.233:1234"]` |
| `chroma_mode` | str (`"http"\|"embedded"`) | Yes | `"http"` | Determines whether vectors are proxied to a remote Chroma HTTP server or stored in the embedded engine. | `"embedded"` |
| `chroma_url` | str? | Conditional | `"http://127.0.0.1:8000"` | Remote Chroma endpoint used when `chroma_mode` is `"http"`. Ignored for embedded mode. | `"http://192.168.1.42:8000"` |
| `chroma_persist_dir` | str? | Conditional | `"/data/chroma"` | Filesystem directory for embedded Chroma persistence. Required when `chroma_mode` is `"embedded"`. | `"/data/chroma"` |
| `collection_name` | str | Yes | `"cathedral"` | Chroma collection that stores embeddings for the orchestrator. | `"cathedral"` |
| `allowed_domains` | list(str) | Yes | `["light","switch","scene"]` | Home Assistant domains exposed to MPC tools. | `["light","switch","scene","media_player"]` |
| `temperature` | float | Yes | `0.7` | Default sampling temperature applied to LM Studio compatible hosts. | `0.6` |
| `top_p` | float | Yes | `0.9` | Default nucleus sampling value passed through to upstream models. | `0.85` |
| `upserts_enabled` | bool | Yes | `true` | Enables real-time embedding upserts to Chroma. Disable to operate in read-only replay mode. | `false` |

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
  "upserts_enabled": true
}
```

Apply via `POST /api/options` to hot-load the configuration; persist the same structure back to Home Assistant Supervisor to survive restarts.
