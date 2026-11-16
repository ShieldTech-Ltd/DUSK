# dusk-gate: the deterministic /v1/gate HTTP service and optional integration clients.
FROM python:3.13.18-alpine3.24@sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==84.1.0 wheel==0.47.0 \
    && pip install --no-cache-dir -e . \
    && pip uninstall --yes setuptools wheel pip \
    && addgroup -g 1000 dusk \
    && adduser -D -u 1000 -G dusk dusk \
    && mkdir -p /app/state \
    && chown -R dusk:dusk /app

USER 1000

ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=8000 \
    DUSK_DEMO_INTEGRATIONS=false \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--worker-tmp-dir", "/tmp", "--no-control-socket", "dusk_harness.api:app"]
