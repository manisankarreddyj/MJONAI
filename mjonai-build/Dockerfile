# ==============================================================================
# MJONAI Institutional Autonomous Trading Engine Dockerfile
# Multi-stage secure build with rootless user execution & healthchecks
# ==============================================================================

FROM python:3.12-slim AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime image
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set Indian Standard Time
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY --from=builder /install /usr/local
COPY . /app

# Create unprivileged runner
RUN useradd -u 10001 -m -s /bin/bash mjonai && \
    mkdir -p /app/data/cache /app/data/backups /app/logs && \
    chown -R mjonai:mjonai /app

USER mjonai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/live || exit 1

CMD ["python", "scripts/daemon_runner.py"]
