# Patch 0122 – Workspace-scoped session updates

## Summary
- Require `workspace_id` alongside `thread_id` for all mutation helpers in the session manager.
- Prevent cross-workspace contamination by scoping SQL updates to the composite primary key.
- No changes to schemas, APIs, or options; release tracked as version 1.1.3.

## Rationale
Recent schema extensions introduced additional metadata writes, but the update helpers only keyed on `thread_id`. In environments that recycle thread identifiers across workspaces, this could allow one workspace to alter another's session record. The new signatures ensure every mutating helper uses both `workspace_id` and `thread_id`, matching the table's primary key.

## Operational Impact
- Existing databases require no migration because the schema is unchanged.
- Callers must supply `workspace_id` when updating host metadata, health state, or Chroma collection references.
- The background TTL pruning and status endpoints operate unchanged, and no new configuration toggles are introduced.
