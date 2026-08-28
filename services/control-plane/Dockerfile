# Independently deployable DUSK production control plane.
FROM python:3.13.11-slim-bookworm@sha256:20080e807bfc404f8450b185cf0fc95d553462673598549613735f70a5b4d5d0

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==83.0.0 wheel==0.47.0 \
    && pip install --no-cache-dir . \
    && pip uninstall --yes setuptools wheel pip \
    && useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin dusk \
    && chown -R dusk:dusk /app

USER 10001:10001

ENV DUSK_CP_ENVIRONMENT=production \
    DUSK_CP_HOST=0.0.0.0 \
    DUSK_CP_PORT=8080 \
    DUSK_CP_API_DOCS_ENABLED=false \
    DUSK_CP_V2_ENABLED=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/livez', timeout=3)"]

CMD ["dusk-control-plane"]
