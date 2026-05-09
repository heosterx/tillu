# TILLU Engine — n8n on HuggingFace Spaces
# ==========================================
# Free hosting: CPU Basic (2 vCPU, 16GB RAM, 50GB disk)
# Database: Supabase PostgreSQL (persistent — survives restarts)
# Timezone: Asia/Kolkata (IST)
#
# HF Space Secrets to set (Settings → Variables and secrets):
#   N8N_ENCRYPTION_KEY       — random 32-char hex
#   DB_POSTGRESDB_HOST       — your Supabase host (db.xxx.supabase.co)
#   DB_POSTGRESDB_DATABASE   — postgres
#   DB_POSTGRESDB_USER       — postgres
#   DB_POSTGRESDB_PASSWORD   — your Supabase DB password
#   TILLU_GATEWAY_URL        — https://tillu-gateway.onrender.com
#   N8N_BASIC_AUTH_USER      — admin
#   N8N_BASIC_AUTH_PASSWORD  — your strong password
#   WEBHOOK_URL              — https://tillu-ai-tillu-engine.hf.space

FROM node:22-alpine

USER root

# ── System dependencies ───────────────────────────────────────────────────────
RUN apk add --no-cache \
    git \
    python3 \
    py3-pip \
    make \
    g++ \
    build-base \
    cairo-dev \
    pango-dev \
    chromium \
    postgresql-client \
    curl \
    jq \
    tzdata

# ── Timezone: IST ─────────────────────────────────────────────────────────────
ENV TZ=Asia/Kolkata
RUN cp /usr/share/zoneinfo/Asia/Kolkata /etc/localtime && \
    echo "Asia/Kolkata" > /etc/timezone

# ── Chromium for Playwright nodes ─────────────────────────────────────────────
ENV PUPPETEER_SKIP_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser

# ── n8n install — pinned to last stable release on Node 22 ───────────────────
RUN npm install -g n8n@2.16.1 --ignore-scripts=false

# ── n8n data directory ────────────────────────────────────────────────────────
ARG BASE_PATH=/root/.n8n
RUN mkdir -p $BASE_PATH/workflows && chmod -R 777 $BASE_PATH

# ── Copy TILLU workflows ──────────────────────────────────────────────────────
COPY workflows/ /root/.n8n/workflows/

# ── n8n configuration ─────────────────────────────────────────────────────────
ENV N8N_PORT=7860
ENV N8N_PROTOCOL=https
ENV N8N_HOST=0.0.0.0
ENV GENERIC_TIMEZONE=Asia/Kolkata
ENV N8N_RUNNERS_ENABLED=true
ENV NODE_FUNCTION_ALLOW_BUILTIN=*
ENV NODE_FUNCTION_ALLOW_EXTERNAL=*
ENV N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=false
ENV EXECUTIONS_DATA_PRUNE=true
ENV EXECUTIONS_DATA_MAX_AGE=168

# Use SQLite — no external DB needed for n8n's own storage.
# TILLU data lives in Supabase; n8n only needs SQLite for workflows/credentials.
# Workflows are baked into the image so nothing is lost on restart.
ENV DB_TYPE=sqlite
ENV DB_SQLITE_VACUUM_ON_STARTUP=true

# Basic auth (set via HF Secrets)
ENV N8N_BASIC_AUTH_ACTIVE=true

WORKDIR /data

EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:7860/healthz || exit 1

CMD ["n8n", "start"]
