# Cathedral MPC Server MVP (Home Assistant Orchestrator Add-on)

This repository contains a production-ready MVP that implements:
- A Home Assistant **Supervisor add-on** which runs a **Relay Orchestrator** exposing OpenAI-compatible endpoints and a WebSocket MPC server.
- A **custom MPC integration UI** for Home Assistant (entities, Options Flow, Coordinator).
- A **Conversation Agent** integration for Assist, routing voice/text to the orchestrator.
- A **Chroma** HTTP client (upserts only; embeddings are computed by **LM Studio** on Windows).
- Acceptance tests and an operator runbook.

## Quick Start (Operator)

1. **Windows host**: Install and run LM Studio (`/v1/*`) and Chroma (HTTP, port 8000).
2. **Copy add-on**: Place `addons/cathedral_orchestrator/` into Home Assistant's local add-ons repo.
3. **Install add-on** in the Add-on Store → Local add-ons → Configure options → Start.
4. **Install integrations**: Copy `custom_components/*` to HA `config/custom_components/`, restart HA, add:
   - “Cathedral MPC” integration (options set orchestrator URL).
   - “Cathedral Agent” (choose as conversation agent in an Assist pipeline).
5. **Run tests**: See `scripts/acceptance/` for cURL and Python scripts.

> **No embeddings or inference occur on the HA node.** All model work is done by LM Studio on Windows. Vectors are written to **Chroma (HTTP)** on Windows.
