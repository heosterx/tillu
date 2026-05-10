# TILLU Daemon — Fly.io Deployment
# ===================================
# Pure Python asyncio background worker.
# No HTTP port needed — Fly.io runs it as a worker process.
# 16 concurrent async loops, self-restarting on failure.

FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user
RUN useradd -m -u 1000 tillu && chown -R tillu:tillu /app
USER tillu

# Health check via a simple file touch (daemon writes heartbeat)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os, time; f='/tmp/daemon_heartbeat'; \
        assert os.path.exists(f) and time.time()-os.path.getmtime(f)<120, 'Daemon dead'" \
    || exit 1

# Start the daemon
CMD ["python", "-m", "daemon.core"]
