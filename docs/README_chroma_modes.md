# Chroma Deployment Modes

## HTTP mode (default)
Set `chroma_mode: "http"` and point `chroma_url` at a reachable Chroma server such as AnythingLLM's managed instance (e.g. `http://127.0.0.1:8000`). The orchestrator communicates purely over HTTP and reuses pooled connections configured at startup.

## Embedded mode (removed)
Embedded persistence is no longer shipped with the add-on. Set `chroma_mode: "http"` and run a LAN-accessible Chroma instance (for example on a dedicated Windows or Linux node). The Home Assistant container no longer bundles the `chromadb` Python package or onnxruntime wheels, preventing build failures on musllinux targets.

## Single-writer switch
Use the `upserts_enabled` flag (`true` or `false`) to control whether the orchestrator writes vectors into Chroma after `/v1/embeddings` calls. Disable this when deferring persistence to AnythingLLM or another downstream service.
