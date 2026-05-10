# TILLU Daemon — HuggingFace Space
# ===================================
# HF Spaces requires HTTP on port 7860.
# This runs the daemon's 16 async loops + a minimal FastAPI health server
# on the same process using asyncio.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces requires UID 1000
RUN useradd -m -u 1000 tillu && chown -R tillu:tillu /app
USER tillu

EXPOSE 7860

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run the daemon with embedded HTTP health server
CMD ["python", "-m", "daemon.hf_runner"]
