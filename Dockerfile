ARG BUILD_FROM=python:3.11-alpine3.18
FROM ${BUILD_FROM}

# System deps
RUN apk add --no-cache bash curl && \
    pip3 install --no-cache-dir --break-system-packages \
    fastapi==0.111.0 uvicorn==0.30.1 httpx==0.27.0

WORKDIR /app
COPY . /app/

# Ensure data dir exists (HA mounts /data, local dev needs it)
RUN mkdir -p /data && chmod +x /app/run.sh

EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -sf http://localhost:8099/api/status || exit 1

CMD ["/app/run.sh"]
