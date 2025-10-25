ARG BUILD_FROM=ghcr.io/home-assistant/amd64-debian:bookworm
FROM $BUILD_FROM

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps for Python builds and runtime
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-pip python3-dev \
      build-essential cmake git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

# Copy source
COPY orchestrator/ /opt/app/origin/
COPY run.sh /opt/app/run.sh
RUN chmod +x /opt/app/run.sh

# Create venv (PEP-668-compliant) and install runtime deps
RUN python3 -m venv /opt/venv \
 && . /opt/venv/bin/activate \
 && pip install --upgrade pip \
 && pip install --no-cache-dir \
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

# Expose runtime env so run.sh can find the venv python/pip
ENV PATH="/opt/venv/bin:${PATH}"

# Move app code to /opt/app/orchestrator (keeps your current run.sh happy)
RUN mv /opt/app/origin /opt/app/orchestrator

EXPOSE 8001 5007
CMD ["/opt/app/run.sh"]
