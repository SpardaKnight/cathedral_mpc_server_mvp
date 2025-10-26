ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip bash curl jq ca-certificates \
    build-essential git && \
    rm -rf /var/lib/apt/lists/*

# Create and use venv at /opt/venv
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/python -m pip install --no-cache-dir --upgrade pip

WORKDIR /opt/app

# Copy orchestrator and entrypoint
COPY orchestrator /opt/app/orchestrator
COPY run.sh /opt/app/run.sh
RUN chmod +x /opt/app/run.sh

# Copy s6 service definitions
COPY rootfs/ /
RUN chmod +x /etc/services.d/cathedral/run /etc/services.d/cathedral/finish

# Pinned runtime deps
RUN /opt/venv/bin/pip install --no-cache-dir \
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
