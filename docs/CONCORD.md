# Cathedral Concord for Home Assistant

The Cathedral Orchestrator add-on inherits Cathedral's Concord doctrine with adjustments for Home Assistant Supervisor realities. These rules are non-negotiable:

1. **No fabricated tests** – Supervisor images are validated via real Docker builds only. Unit mocks, pytest suites, or synthetic CI scaffolds are prohibited.
2. **Schema discipline** – `lm_hosts` is a `list(url)`; options must align with the published schema before merging. All hot-apply payloads match `config.yaml`/`config.json`.
3. **LAN-only posture** – Ports `8001` and `5005` remain bound inside the Supervisor network. Expose them externally only behind an operator-managed proxy.
4. **Single-writer rule** – Exactly one orchestrator instance writes to `/data/sessions.db` and `/data/chroma`. External tools use read-only access.
5. **No secrets in logs** – Supervisor tokens and MPC credentials are never printed. Logging stays structured via `logging_config.py` and routes to Home Assistant's log collector.
6. **Stable ports and paths** – Runtime surfaces, volume mounts, and entrypoints must not drift without explicit changelog notes and schema updates.
7. **Options discipline** – Every new option requires schema updates, MegaDoc refresh, and operator guidance. Default changes must be documented in both YAML and JSON manifests.
8. **No silent import pruning** – Python dependencies must remain explicit in `requirements.txt` equivalent within the Dockerfile. Supervisor caches rely on deterministic wheels.
9. **Reload aware** – After adding the repository, operators must trigger **⋮ → Reload**. Documentation must continue to warn about this gotcha.
10. **HA parity** – Development helpers (like `dev/venv/activate.sh`) mirror the Debian + `/opt/venv` environment to prevent drift between local and Supervisor deployments.
