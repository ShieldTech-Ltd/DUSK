FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app

# Install the DUSK package and all its declared dependencies from pyproject.toml.
# Build context is the repo root (image_build_context: ".").
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir ".[runtime]" 2>/dev/null \
 || pip install --no-cache-dir -e "." \
 && pip install --no-cache-dir cryptography

# Copy the runtime server after the dependency layer so cache is reused on
# server-only changes.
COPY workers/dusk-runtime/runtime_server.py ./runtime_server.py

# Run as a non-root user.
RUN useradd --system --no-create-home --uid 1001 dusk-runtime
USER dusk-runtime

EXPOSE 8080

CMD ["python", "runtime_server.py"]
