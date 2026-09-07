FROM python:3.12-slim

WORKDIR /app

# Install DUSK dependencies from the repo root.
# Build context is the repo root (image_build_context: ".").
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir cryptography

# Copy the DUSK package.
COPY src/dusk ./src/dusk

# Copy the runtime server.
COPY workers/dusk-runtime/runtime_server.py ./runtime_server.py

EXPOSE 8080

CMD ["python", "runtime_server.py"]
