ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python
RUN apk add --no-cache python3 py3-pip bash curl jq &&     python3 -m pip install --no-cache-dir --upgrade pip

# Install pinned Python dependencies
RUN pip install --no-cache-dir     fastapi==0.115.0     uvicorn[standard]==0.30.6     httpx==0.27.2     pydantic==2.9.2     websockets==12.0     starlette==0.38.5     chromadb==0.5.4     tiktoken==0.7.0

# Copy orchestrator code and entrypoint
COPY orchestrator /opt/orchestrator
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENV PYTHONUNBUFFERED=1

CMD [ "/run.sh" ]
