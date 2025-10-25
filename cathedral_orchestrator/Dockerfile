ARG BUILD_FROM=ghcr.io/home-assistant/amd64-debian:bookworm
FROM $BUILD_FROM

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Debian base; install Python and tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip bash curl jq ca-certificates \
    build-essential git && \
    python3 -m venv /opt/venv && \
    pip install --no-cache-dir --upgrade pip

WORKDIR /opt/app

# Copy orchestrator and entrypoint
COPY orchestrator/ /opt/app/orchestrator/
COPY run.sh /opt/app/run.sh
RUN chmod +x /opt/app/run.sh

# Pinned runtime deps
RUN pip install --no-cache-dir \
      fastapi==0.115.0 \
      uvicorn==0.30.6 \
      httpx==0.27.2 \
      pydantic==2.9.2 \
      tiktoken==0.7.0 \
      websockets==12.0 \
      uvloop==0.19.0 \
      httptools==0.6.1 \
      aiosqlite==0.20.0 \
      chromadb==0.5.12

EXPOSE 8001 5005
CMD ["/opt/app/run.sh"]
