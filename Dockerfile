FROM python:3.12-slim

ARG GRAPHIFYY_VERSION=0.8.38

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    QA_AGENT_DATA_DIR=/app/data \
    QA_AGENT_DATABASE_PATH=/app/data/qa_agent.sqlite \
    GRAPHIFY_BIN=graphify

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install "graphifyy==${GRAPHIFYY_VERSION}" \
    && pip install .

RUN graphify --version

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "qa_agent_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
