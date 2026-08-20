# agent-demo: model -> extract action -> /v1/gate -> mock-PROD.
# USE_REAL_BEDROCK=false (compose default) needs no AWS credentials.
# Build context is this example's own root (see compose.yml) since
# harness.py needs the dusk package (BedrockAdapter) installed alongside
# its own deps.
FROM python:3.11-slim-bookworm@sha256:2e32f7d302adc1c37428355c1e646897c0c53f4fd60b6a551245fb90ee129f91

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip==26.2.1 setuptools==83.0.0 wheel==0.47.0 \
    && pip install --no-cache-dir -e .

COPY agent-demo/requirements.txt ./agent-demo/requirements.txt
RUN pip install --no-cache-dir -r agent-demo/requirements.txt \
    && pip uninstall --yes setuptools wheel pip \
    && useradd --create-home --uid 1000 agentdemo \
    && chown -R agentdemo:agentdemo /app

USER agentdemo

COPY agent-demo/bedrock_client.py agent-demo/mock_bedrock.py agent-demo/harness.py agent-demo/run_scenario.py ./

ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "run_scenario.py"]
