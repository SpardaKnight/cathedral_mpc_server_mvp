# Patch 0140 – SSE graceful close and legacy models alias

- The chat completions relay now treats `httpx.StreamClosed` as a normal EOF and always appends the SSE `data: [DONE]` trailer so clients no longer log premature-close errors.
- Added `/api/v0/models` as a direct alias to `/v1/models` for legacy AnythingLLM compatibility checks.
- Bumped the add-on manifest and changelog to publish the streaming fix.
