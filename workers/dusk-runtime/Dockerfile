# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.13.18-alpine3.24@sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e

# hadolint ignore=DL3006
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY workers/dusk-runtime/runtime-requirements.lock ./runtime-requirements.lock
RUN python -m pip install --require-hashes --no-deps --only-binary=:all: -r runtime-requirements.lock
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m pip install --no-build-isolation --no-compile --no-deps . \
    && python -m pip check

# hadolint ignore=DL3006
FROM ${PYTHON_IMAGE} AS runtime
ARG OCI_REVISION=unknown
LABEL org.opencontainers.image.title="DUSK native policy runtime" \
    org.opencontainers.image.source="https://github.com/ShieldTech-Ltd/DUSK" \
    org.opencontainers.image.revision="${OCI_REVISION}" \
    org.opencontainers.image.licenses="Apache-2.0"
COPY dusk-agent-harness/mock-prod/alpine-runtime-patches.sh /tmp/alpine-runtime-patches.sh
RUN sh /tmp/alpine-runtime-patches.sh && rm /tmp/alpine-runtime-patches.sh
RUN addgroup -g 1001 dusk-runtime \
    && adduser -S -D -H -u 1001 -G dusk-runtime dusk-runtime
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
RUN rm -rf /usr/local/lib/python3.13/site-packages/pip* \
    /usr/local/lib/python3.13/site-packages/setuptools* \
    /usr/local/lib/python3.13/site-packages/wheel* \
    /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.13 \
    /usr/local/bin/wheel /root/.cache
WORKDIR /app
COPY --chown=1001:1001 workers/dusk-runtime/runtime_server.py ./runtime_server.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1001:1001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"]
CMD ["python", "runtime_server.py"]
