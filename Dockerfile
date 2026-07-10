# dusk-gate: the /v1/gate HTTP service (core gate + SIE client + trace + n8n).
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[api]" \
    && useradd --create-home --uid 1000 dusk \
    && chown -R dusk:dusk /app

USER dusk

ENV FLASK_HOST=0.0.0.0 \
    FLASK_PORT=8000 \
    DUSK_DEMO_INTEGRATIONS=false

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]

CMD ["python", "-m", "dusk.api"]
