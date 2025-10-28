# Patch 0160 – Orchestrator 0.2.1 model metadata enrichment

- Enrich `/v1/models` with LM Studio-provided context and embedding metadata so desktop clients detect max input tokens without manual overrides.
- Replace the `/api/v0/models` alias with a real LM Studio catalog union that preserves single-host passthrough while merging multi-host inventories.
- Add a runtime `requirements.txt` (including PyYAML) and install it via the Docker build to keep Supervisor images aligned with orchestrator imports.
- Bump the add-on manifests and changelog to version 0.2.1 alongside MegaDoc and runtime surface documentation updates.
