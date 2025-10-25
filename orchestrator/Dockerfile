ARG BUILD_FROM
FROM $BUILD_FROM

# Quieter Python, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Alpine base; install Python toolchain + build deps + tools required by run.sh
RUN apk add --no-cache \
    python3 py3-pip py3-setuptools py3-wheel \
    build-base rust cargo musl-dev \
    bash curl jq

WORKDIR /opt/app

# Copy orchestrator and entrypoint
COPY orchestrator/ /opt/app/orchestrator/
COPY run.sh /opt/app/run.sh
RUN chmod +x /opt/app/run.sh

# Pin runtime deps; keep websockets; add uvloop/httptools/aiosqlite for perf & async DB
RUN pip3 install --no-cache-dir \
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
