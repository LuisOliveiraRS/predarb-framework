FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV DEBUG=false
ENV HYPERLIQUID_TESTNET_EXECUTION_ENABLED=false
ENV HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED=false
ENV HYPERLIQUID_MAINNET_EXECUTION_ENABLED=false
ENV HYPERLIQUID_MAINNET_EXECUTION_AUTHORIZED=false
ENV AI_EXECUTION_AUTHORIZED=false
ENV PAPER_SESSION_AUTO_START=false
ENV SHADOW_RUNTIME_SCHEDULER_ENABLED=false

WORKDIR /app

RUN useradd \
    --create-home \
    --uid 10001 \
    appuser

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN mkdir -p \
        /app/paper_data \
        /app/model_artifacts \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
