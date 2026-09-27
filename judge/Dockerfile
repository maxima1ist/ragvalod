# syntax=docker/dockerfile:1
# Hourly LLM-as-a-judge. Compose runs scripts/judge_loop.py.
# Kubernetes CronJob overrides the command with a single judge_traces.py pass.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir "httpx>=0.28,<1"

COPY scripts/judge_traces.py scripts/judge_loop.py scripts/

CMD ["python", "scripts/judge_loop.py"]
