# Patch 0121: Actions Lockdown for Codex Control

## Summary
- Updated the addon-smoke-build workflow to run only via manual or Codex-triggered dispatch events while preserving its build steps.
- Documented the new guardrail in AGENTS.md to prohibit GitHub-hosted automatic Actions triggered by push or pull_request events.

## Rationale
Codex must retain the ability to invoke repository_dispatch workflows without consuming GitHub-hosted runner minutes from automatic push or pull_request triggers. These changes enforce that policy while keeping the smoke build workflow usable for authorized dispatches.
