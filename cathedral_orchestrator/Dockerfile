ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-debian:bookworm
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

# Copy source (use origin and then move to orchestrator to keep run.sh paths)
COPY orchestrator/ /opt/app/origin/
COPY run.sh /opt/app/run.sh
RUN chmod +x /opt/app/run.sh

# Create venv and install runtime deps (PEP 668 compliant)
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

# Move app code to /opt/app/orchestrator (run.sh refers to this path)
RUN mv /opt/app/origin /opt/app/orchestrator

EXPOSE 8001 5005
CMD ["/opt/app/run.sh"]
