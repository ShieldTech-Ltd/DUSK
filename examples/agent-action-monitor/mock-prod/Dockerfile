# mock-prod: dummy downstream controller/DB target for the DUSK example.
FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==83.0.0 wheel==0.47.0 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall --yes setuptools wheel pip \
    && useradd --create-home --uid 1000 mockprod \
    && chown -R mockprod:mockprod /app

USER mockprod

COPY app.py .

ENV MOCK_PROD_HOST=0.0.0.0 \
    MOCK_PROD_PORT=9000 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:9000/health', timeout=3)"]

CMD ["gunicorn", "--bind", "0.0.0.0:9000", "--workers", "1", "--threads", "2", "--worker-tmp-dir", "/tmp", "--no-control-socket", "app:app"]
