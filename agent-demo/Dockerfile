# agent-demo: model -> extract action -> /v1/gate -> mock-PROD.
# USE_REAL_BEDROCK=false (compose default) needs no AWS credentials.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 agentdemo \
    && chown -R agentdemo:agentdemo /app

USER agentdemo

COPY bedrock_client.py mock_bedrock.py harness.py run_scenario.py ./

CMD ["python", "run_scenario.py"]
