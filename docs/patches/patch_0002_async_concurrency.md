# Patch 0002: Async concurrency uplift

## Summary
- Install uvloop/httptools/websockets/aiosqlite and required shell tools in the orchestrator add-on image
- Rework the session store to use aiosqlite for non-blocking persistence
- Pool HTTP clients, enable multi-worker Uvicorn, and adjust MPC server session handling for async APIs
- Normalize Chroma client metadata/result formatting to avoid blocking set-literal evaluation

## Testing
- `python - <<'PY'
import importlib
mods = [
 "addons.cathedral_orchestrator.orchestrator.main",
 "addons.cathedral_orchestrator.orchestrator.mpc_server",
 "addons.cathedral_orchestrator.orchestrator.toolbridge",
 "addons.cathedral_orchestrator.orchestrator.vector.chroma_client",
 "addons.cathedral_orchestrator.orchestrator.sessions",
]
for m in mods:
    importlib.import_module(m)
    print("OK:", m)
PY`
- `ruff check addons/cathedral_orchestrator/orchestrator/main.py addons/cathedral_orchestrator/orchestrator/mpc_server.py`
- `ruff check addons/cathedral_orchestrator/orchestrator/sessions.py`
- `ruff check addons/cathedral_orchestrator/orchestrator/vector/chroma_client.py`
- `mypy --follow-imports=skip addons/cathedral_orchestrator/orchestrator/main.py`
- `mypy --follow-imports=skip addons/cathedral_orchestrator/orchestrator/mpc_server.py`
- `mypy --follow-imports=skip addons/cathedral_orchestrator/orchestrator/sessions.py`
- `pytest`
