# Home Assistant Installation Guide

## Add from Repository
1. Open **Settings → Add-ons → Add-on Store**.
2. Click **⋮ (overflow) → Repositories**.
3. Paste `https://github.com/SpardaKnight/cathedral_mpc_server_mvp` (no `.git` suffix) and press **Add**.
4. After adding, press **⋮ → Reload**. The store does not automatically index new custom repositories.
5. Locate **Cathedral Orchestrator** under the *Cathedral* section and press **Install**.

## Local Add-on Install
- For offline deployments, copy the repository into `/addons/cathedral_orchestrator` on the Supervisor host (via SSH or Samba add-on).
- Ensure the directory retains `cathedral_orchestrator/Dockerfile`, manifests, and the `orchestrator/` package.
- Return to the Add-on Store and press **⋮ → Reload**; the add-on will appear under *Local add-ons*.

## Configure Options
1. Open the add-on configuration tab.
2. Populate options using the schema from [docs/schemas/ADDON_OPTIONS.md](../schemas/ADDON_OPTIONS.md).
3. Save and restart the add-on. Hot updates can be applied later via `POST /api/options` but persist changes through the UI to survive reboots.

## Reload Gotcha
- Any time the repository URL changes or branches are updated, trigger **⋮ → Reload**. Without reloading, Supervisor continues serving cached metadata.

## Forcing Rebuilds
- Supervisor rebuilds the image when `version` in `config.yaml`/`config.json` changes. Bump the patch version (e.g., `0.1.3` → `0.1.4`) to force a rebuild after modifying Dockerfile dependencies.
- Alternatively, uninstall and reinstall the add-on; Supervisor will rebuild using the latest manifests.
