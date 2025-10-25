# Chroma Deployment Modes

## HTTP mode (default)
Set `chroma_mode: "http"` and point `chroma_url` at a reachable Chroma server such as AnythingLLM's managed instance (e.g. `http://127.0.0.1:8000`). The orchestrator will proxy embeddings over HTTP and reuse pooled connections configured at startup.

## Embedded mode
Set `chroma_mode: "embedded"` to run the Chroma client in-process. Embeddings and metadata will persist under `/data/chroma`, so ensure the add-on data volume has sufficient space. The Docker image now bundles `chromadb==0.5.12`, enabling embedded mode without additional packages.

## Single-writer switch
Use the `upserts_enabled` flag (`true` or `false`) to control whether the orchestrator writes vectors into Chroma after `/v1/embeddings` calls. Disable this when deferring persistence to AnythingLLM or another downstream service.
