# Patch 0141 – Chat completions static LM Studio relay

- Replace the `/v1/chat/completions` handler with a raw streaming proxy that forwards requests to LM Studio at `http://192.168.1.175:1234/v1/chat/completions`.
- Document the dedicated relay host in the runtime surface spec and MegaDoc so operators know completions ignore the configured host list.
- Bump the add-on manifest and changelog to publish the new relay behavior.
