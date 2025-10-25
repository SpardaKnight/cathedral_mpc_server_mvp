# Patch 0003: Dual-mode Chroma client and upsert switch

## Summary
- add chromadb to the orchestrator add-on image to unlock embedded persistence
- extend the Chroma client to support HTTP and embedded configurations with pooled connections
- wire runtime options for persist directory and upsert enablement while preserving GPU-hosted embedding flow
- harden the async session store with SQLite UPSERT semantics and synchronous tuning

## Testing
- `pytest`
- `ruff check cathedral_orchestrator/orchestrator`
- `mypy --follow-imports=skip cathedral_orchestrator/orchestrator`
