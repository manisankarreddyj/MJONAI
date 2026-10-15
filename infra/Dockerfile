# ==============================================================================
# MJONAI Institutional Autonomous Trading Engine Dockerfile
# Multi-stage secure build with rootless user execution & healthchecks
# ADR-0008: build context = repo root; entrypoint = apps/runtime/main.py
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

# Create unprivileged runner (ADR-0008: runtime data at repo root)
RUN useradd -u 10001 -m -s /bin/bash mjonai && \
    mkdir -p /app/storage /app/cache /app/backups /app/logs && \
    chown -R mjonai:mjonai /app

USER mjonai

# P0-APPS-2: the old HEALTHCHECK curled localhost:8000/api/health/live, but
# THIS image runs apps/runtime/main.py — a headless engine with no HTTP
# server (the API lives in apps/web, a separate deployable; EXPOSE 8000 is
# dropped for the same reason). Every probe failed, so the container was
# marked unhealthy in a restart loop. Probe engine-process liveness via
# /proc instead of a port it never opens.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os,sys; ok=any('apps/runtime/main.py' in open('/proc/'+p+'/cmdline','rb').read().decode(errors='ignore') for p in os.listdir('/proc') if p.isdigit()); sys.exit(0 if ok else 1)"

CMD ["python", "apps/runtime/main.py"]
