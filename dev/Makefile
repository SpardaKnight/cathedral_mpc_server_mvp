build_amd64:
	docker buildx build . \
	 --file cathedral_orchestrator/Dockerfile \
	 --platform linux/amd64 --pull \
	 --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-debian:bookworm \
	 --label "io.hass.type=addon" \
	 --label "io.hass.arch=amd64" \
	 --label "io.hass.name=Cathedral Orchestrator" \
	 --label "io.hass.version=0.1.1"
