build_amd64:
	docker buildx build . \
	 --file cathedral_orchestrator/Dockerfile \
	 --platform linux/amd64 --pull \
	 --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
