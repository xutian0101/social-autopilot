FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DRY_RUN=true \
    TIMEZONE=Asia/Shanghai

COPY pyproject.toml README.md ./
COPY social_autopilot ./social_autopilot
COPY content ./content
COPY reports ./reports

RUN pip install --no-cache-dir -e .

# Default: daily pipeline (override with docker compose / cron)
CMD ["python", "-m", "social_autopilot", "run-daily"]
