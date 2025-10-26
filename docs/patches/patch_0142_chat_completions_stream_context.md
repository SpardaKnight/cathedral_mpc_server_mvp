# Patch 0142 – Chat completions stream context

- Fix the `/v1/chat/completions` relay to enter `httpx.AsyncClient.stream` via `async with`, preserving byte-accurate SSE passthrough to AnythingLLM.
- Note the corrected streaming contract in the MegaDoc and schema reference so operators understand the async context requirement.
- Bump the add-on manifests and changelog to release version 1.1.15 with the streaming stability patch.
