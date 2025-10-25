# Repository Structure

```
cathedral_mpc_server_mvp/
├── README.md                     # Entry overview with install + schema links
├── STATUS.md                     # Release readiness checklist
├── RUNBOOK.md                    # Incident recovery playbook
├── cathedral_orchestrator/       # Home Assistant add-on payload
│   ├── Dockerfile                # Debian bookworm base + /opt/venv bootstrap
│   ├── build.json                # Supervisor build metadata (arch, base image)
│   ├── config.yaml               # Primary manifest consumed by Supervisor
│   ├── config.json               # JSON mirror for tooling parity
│   ├── run.sh                    # Entrypoint invoked by Supervisor
│   └── orchestrator/             # Python package shipped inside the add-on
│       ├── main.py               # FastAPI app exposing OpenAI + admin routes
│       ├── mpc_server.py         # MPC router and server state machine
│       ├── sessions.py           # SQLite-backed session store (WAL)
│       ├── sse.py                # Streaming helper for Chat Completions
│       ├── toolbridge.py         # Home Assistant tool execution bridge
│       ├── vector/chroma_client.py # Chroma integration (HTTP + embedded)
│       └── logging_config.py     # Structured logging setup
├── custom_components/            # Reserved for future HA integrations
├── docs/                         # MegaDoc, schemas, specs, operations, patch logs
│   ├── MegaDoc.md                # Canonical one-stop reference
│   ├── __index__.md              # Documentation landing page
│   ├── CONCORD.md                # Cathedral Concord doctrine for HA
│   ├── CHANGELOG.md              # Docset change history
│   ├── structure.md              # This file
│   ├── schemas/                  # Supervisor option schemas
│   ├── specs/                    # Runtime/build/security specifications
│   ├── operations/               # Operator how-tos (install, smoke build)
│   ├── src/                      # Module-level doclets
│   └── patches/                  # Historical patch logs (source changes)
├── dev/                          # Opt-in local environment mirror
│   ├── venv/activate.sh          # Script to create add-on-aligned virtualenv
│   └── Makefile                  # Mirror docker buildx invocation
└── scripts/                      # Support scripts referenced by RUNBOOK
```

The add-on folder `cathedral_orchestrator/` is what Supervisor consumes. Docs and `dev/` are development-time aids and do not ship inside the container image.
