# Patch 0171 — LM host probe isolation and diagnostics endpoint

- Refresh LM host pools and catalog aggregation with per-host HTTPX clients so one timeout cannot poison subsequent probes.
- Log the exception class alongside errors and retain the latest probe snapshot for `/debug/probe`.
- Add `/debug/probe` to the FastAPI surface for on-demand host diagnostics and document the endpoint across the MegaDoc and runtime specs.
- Bump the add-on manifest to version 0.2.11 and align the changelog entries.
