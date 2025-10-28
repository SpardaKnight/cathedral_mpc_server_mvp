# Patch 0154 – Orchestrator 0.1.6 stabilization

## Summary
- bump Supervisor manifests to version 0.1.6 and align CHANGELOG with the release notes
- restore AnythingLLM agents.* schema with stable params/capabilities and normalize resources discovery responses
- harden the /v1/chat/completions SSE relay, make the session pruner thread-safe with synchronous SQLite pruning, and ensure Chroma collections resolve with a v2-first, v1-fallback flow

## Testing
- ruff check cathedral_orchestrator/orchestrator
- mypy cathedral_orchestrator/orchestrator
- pytest -q tests/unit
