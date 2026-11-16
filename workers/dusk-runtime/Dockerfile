# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

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
ARG DEBIAN_SNAPSHOT=20261115T120000Z
ARG OCI_REVISION=unknown
LABEL org.opencontainers.image.title="DUSK native policy runtime" \
    org.opencontainers.image.source="https://github.com/ShieldTech-Ltd/DUSK" \
    org.opencontainers.image.revision="${OCI_REVISION}" \
    org.opencontainers.image.licenses="Apache-2.0"
RUN sed --in-place \
      --expression="s|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}|g" \
      --expression="s|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}|g" \
      /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get upgrade --yes \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' apt)" ge '3.0.4' \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libapt-pkg7.0)" ge '3.0.4' \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' zlib1g)" ge '1:1.3.dfsg+really1.3.1-1+deb13u1' \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --no-create-home --uid 1001 dusk-runtime
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
