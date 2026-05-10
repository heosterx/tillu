# TILLU WebSearch v2 - HuggingFace Space
# SearXNG (primary) + DDG JSON + Google Lite fallbacks + Playwright

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates fonts-liberation fonts-noto-color-emoji \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 \
    libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libxcomposite1 \
    libxdamage1 libxfixes3 libxkbcommon0 libxrandr2 libxshmfence1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .

RUN useradd -m -u 1000 tillu && chown -R tillu:tillu /app
USER tillu
ENV PLAYWRIGHT_BROWSERS_PATH=/home/tillu/.cache/ms-playwright
RUN playwright install chromium

EXPOSE 7860
ENV PORT=7860
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=15s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
