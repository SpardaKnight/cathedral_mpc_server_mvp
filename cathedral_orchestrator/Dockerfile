ARG BUILD_FROM
FROM $BUILD_FROM

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-setuptools python3-wheel \
    build-essential rustc cargo cmake bash curl jq ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app
COPY orchestrator/ /opt/app/orchestrator/

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      fastapi==0.115.0 \
      uvicorn==0.30.6 \
      httpx==0.27.2 \
      pydantic==2.9.2 \
      tiktoken==0.7.0 \
      websockets==12.0 \
      uvloop==0.19.0 \
      httptools==0.6.1 \
      aiosqlite==0.20.0
# No chromadb here. Chroma is external over HTTP.

COPY rootfs/ /
RUN chmod +x /etc/services.d/cathedral/run /etc/services.d/cathedral/finish /opt/app/start.sh

EXPOSE 8001 5005
