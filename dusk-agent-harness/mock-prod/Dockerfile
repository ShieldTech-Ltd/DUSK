# mock-prod: dummy downstream controller/DB target for the DUSK example.
FROM python:3.13.18-alpine3.24@sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==84.1.0 wheel==0.47.0 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall --yes setuptools wheel pip \
    && addgroup -g 1000 mockprod \
    && adduser -D -u 1000 -G mockprod mockprod \
    && chown -R mockprod:mockprod /app

USER 1000

COPY app.py .

ENV MOCK_PROD_HOST=0.0.0.0 \
    MOCK_PROD_PORT=9000 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:9000/health', timeout=3)"]

CMD ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "1", "--threads", "2", "--worker-tmp-dir", "/tmp", "--no-control-socket", "app:app"]
