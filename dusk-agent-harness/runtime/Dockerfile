# runtime: model -> extract action -> /v1/gate -> mock-PROD.
# USE_REAL_BEDROCK=false (compose default) needs no AWS credentials.
# Build context is this example's own root (see compose.yml) since
# harness.py needs the dusk package (BedrockAdapter) installed alongside
# its own deps.
FROM python:3.13.18-alpine3.24@sha256:9ef1a599f863231c3d91e941389bfdc4a2d6070557243d54df1a4e57015b960e

WORKDIR /app

RUN apk upgrade --no-cache

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==84.1.0 wheel==0.47.0 \
    && pip install --no-cache-dir -e .

COPY runtime/requirements.txt ./runtime/requirements.txt
RUN pip install --no-cache-dir -r runtime/requirements.txt \
    && pip uninstall --yes setuptools wheel pip \
    && addgroup -g 1000 agentdemo \
    && adduser -D -u 1000 -G agentdemo agentdemo \
    && chown -R agentdemo:agentdemo /app

USER 1000

COPY models/ ./models/
COPY runtime/bedrock_client.py runtime/mock_bedrock.py runtime/harness.py \
    runtime/load_driver.py runtime/run_scenario.py ./

ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "run_scenario.py"]
