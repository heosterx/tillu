# TILLU — Complete Setup Guide

> **TILLU runs. TILLU watches. TILLU learns. TILLU thinks. Whether you're there or not.**

This guide walks you through every step to get TILLU running — from zero to a fully operational, perpetually-active personal AI backend.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Account Setup (Free Services)](#3-account-setup-free-services)
4. [Clone & Install](#4-clone--install)
5. [Supabase Setup](#5-supabase-setup)
6. [Redis Setup (Upstash)](#6-redis-setup-upstash)
7. [API Keys](#7-api-keys)
8. [Environment Configuration](#8-environment-configuration)
9. [Run Locally](#9-run-locally)
10. [Run with Docker](#10-run-with-docker)
11. [Deploy to Render (Production)](#11-deploy-to-render-production)
12. [Deploy Hugging Face Embedding Space](#12-deploy-hugging-face-embedding-space)
13. [n8n Workflow Setup](#13-n8n-workflow-setup)
14. [Keepalive Configuration](#14-keepalive-configuration)
15. [Verify Everything Works](#15-verify-everything-works)
16. [Troubleshooting](#16-troubleshooting)
17. [Cost Summary](#17-cost-summary)

---

## 1. Architecture Overview

TILLU runs as **three concurrent processes** that communicate exclusively via Redis Pub/Sub:

```
┌──────────────────────────────────────────────────────────┐
│                      CLIENTS                              │
│         WhatsApp / Web App / Mobile / API                 │
└─────────────────────┬────────────────────────────────────┘
                      │ HTTPS + Bearer Token
                      ▼
┌──────────────────────────────────────────────────────────┐
│  GATEWAY  (FastAPI)     port 8000                         │
│  • Receives all messages                                  │
│  • Runs transformer pipeline                              │
│  • Assembles 7-tier context                               │
│  • Routes to correct chain                                │
│  • Streams events via SSE                                 │
└──────────┬───────────────────────────────────────────────┘
           │
    Redis Pub/Sub (Upstash)
           │
┌──────────┴──────────────────────────────────────────────┐
│  DAEMON  (Python asyncio)   11 concurrent loops          │
│  • Financial watcher (15m)                               │
│  • News scanner (10m)                                    │
│  • Web change detector (30m)                             │
│  • Emotion trend tracker (30m)                           │
│  • Pattern recognition (1h)                              │
│  • + 6 more loops                                        │
└─────────────────────────────────────────────────────────┘

External Services:
  Supabase (PostgreSQL + pgvector) — persistent storage
  Upstash Redis                    — cache + pub/sub
  Groq API                         — primary LLM (free)
  Hugging Face                     — embeddings + NLP
  SearXNG (self-hosted)            — private web search
```

---

## 2. Prerequisites

### Required
| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | [python.org](https://python.org) |
| Git | any | [git-scm.com](https://git-scm.com) |
| Docker + Docker Compose | 24+ | [docker.com](https://docker.com) |

### Check your versions
```bash
python3 --version    # must be 3.10+
docker --version     # must be 24+
docker compose version
git --version
```

---

## 3. Account Setup (Free Services)

Create accounts on these platforms before starting. All have free tiers sufficient for TILLU.

### Required Accounts

| Service | URL | What it's for | Free Tier |
|---------|-----|---------------|-----------|
| **Supabase** | [supabase.com](https://supabase.com) | Database + pgvector | 500MB, 500k requests |
| **Upstash** | [upstash.com](https://upstash.com) | Redis cache + pub/sub | 10k ops/day |
| **Groq** | [console.groq.com](https://console.groq.com) | Primary LLM | 14,400 tokens/min |
| **Hugging Face** | [huggingface.co](https://huggingface.co) | Embeddings + NLP | Rate limited |

### Recommended Accounts (unlock more features)

| Service | URL | What it unlocks |
|---------|-----|-----------------|
| **Cerebras** | [cloud.cerebras.ai](https://cloud.cerebras.ai) | Deep analysis chain |
| **Google AI Studio** | [aistudio.google.com](https://aistudio.google.com) | ReAct agent + Calendar |
| **Brave Search** | [api.search.brave.com](https://api.search.brave.com) | Brave search tool |
| **NewsAPI** | [newsapi.org](https://newsapi.org) | News intelligence |
| **Render** | [render.com](https://render.com) | Production hosting |
| **Notion** | [notion.so](https://notion.so) | Notion tool |

---

## 4. Clone & Install

### Step 1 — Clone the repository

```bash
git clone https://github.com/yourusername/tillu-backend.git
cd tillu-backend
```

### Step 2 — Run the setup script

**Linux / macOS:**
```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\setup.ps1
```

The script will:
- Check Python version
- Create a virtual environment (`venv/`)
- Install all dependencies from `requirements.txt`
- Copy `.env.example` → `.env`

### Step 3 — Manual install (if script fails)

```bash
python3 -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

---

## 5. Supabase Setup

Supabase is TILLU's primary database. It stores all interactions, memories, events, and user data.

### Step 1 — Create a project

1. Go to [supabase.com](https://supabase.com) → **New Project**
2. Choose a name (e.g., `tillu-backend`)
3. Set a strong database password — **save it**
4. Choose the region closest to you
5. Wait ~2 minutes for provisioning

### Step 2 — Enable pgvector

1. In your project, go to **Database → Extensions**
2. Search for `vector`
3. Enable **pgvector**

### Step 3 — Apply the schema

1. Go to **SQL Editor** in your Supabase dashboard
2. Click **New Query**
3. Open `supabase/schema.sql` from this repo
4. Paste the entire contents into the editor
5. Click **Run** (Ctrl+Enter)

You should see: `Success. No rows returned`

This creates all 13 tables:
- `user_profile`, `interactions`, `knowledge_base`
- `news_articles`, `event_queue`, `research_sessions`
- `tasks_goals`, `emotion_log`, `financial_tracking`
- `web_monitors`, `people_knowledge`, `client_registry`
- `emails`, `system_analytics`, `monitor_state`

### Step 4 — Get your credentials

Go to **Settings → API** and copy:

| Variable | Where to find it |
|----------|-----------------|
| `SUPABASE_URL` | Project URL (e.g., `https://abcdef.supabase.co`) |
| `SUPABASE_KEY` | `anon` `public` key |
| `SUPABASE_SERVICE_KEY` | `service_role` key (keep secret!) |
| `SUPABASE_JWT_SECRET` | Settings → API → JWT Settings → JWT Secret |

> **Important:** Use the `service_role` key for `SUPABASE_SERVICE_KEY`. The backend needs it to bypass Row Level Security.

---

## 6. Redis Setup (Upstash)

Upstash provides serverless Redis — perfect for TILLU's free-tier architecture.

### Step 1 — Create a Redis database

1. Go to [console.upstash.com](https://console.upstash.com)
2. Click **Create Database**
3. Name: `tillu-redis`
4. Type: **Regional** (not Global)
5. Region: same as your Supabase region
6. Enable **Eviction** (optional but recommended)
7. Click **Create**

### Step 2 — Get your credentials

From the database details page, copy:

| Variable | Where to find it |
|----------|-----------------|
| `REDIS_URL` | **Redis URL** (starts with `redis://`) |
| `UPSTASH_REDIS_REST_URL` | REST API URL |
| `UPSTASH_REDIS_REST_TOKEN` | REST API Token |

The `REDIS_URL` format looks like:
```
redis://default:YOUR_PASSWORD@YOUR_ENDPOINT.upstash.io:6379
```

> **Local development:** You can use a local Redis instead. Run `docker run -p 6379:6379 redis:7-alpine` and set `REDIS_URL=redis://localhost:6379`.

---

## 7. API Keys

### Groq (Required — Primary LLM)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up / log in
3. Go to **API Keys** → **Create API Key**
4. Copy the key → `GROQ_API_KEY`

Free tier: **14,400 tokens/minute** — more than enough for personal use.

### Hugging Face (Recommended — Embeddings + NLP)

1. Go to [huggingface.co](https://huggingface.co) → Sign up
2. Go to **Settings → Access Tokens**
3. Click **New token** → Type: **Read**
4. Copy the token → `HF_TOKEN`

Without this, TILLU falls back to local sentence-transformers (slower, uses more RAM).

### Cerebras (Recommended — Deep Analysis)

1. Go to [cloud.cerebras.ai](https://cloud.cerebras.ai)
2. Sign up and request API access
3. Go to **API Keys** → create one
4. Copy → `CEREBRAS_API_KEY`

Powers the Analysis chain (Chain 04) for deep reasoning tasks.

### Google AI Studio (Recommended — ReAct Agent + Calendar)

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API Key** → **Create API key**
3. Copy → `GOOGLE_API_KEY`

Powers the ReAct tool agent (Chain 03) and Calendar intelligence.

### Brave Search (Recommended — Web Search)

1. Go to [api.search.brave.com](https://api.search.brave.com)
2. Sign up → **Create App**
3. Copy the API key → `BRAVE_API_KEY`

Free tier: 2,000 queries/month.

### NewsAPI (Optional — News Intelligence)

1. Go to [newsapi.org](https://newsapi.org) → **Get API Key**
2. Copy → `NEWSAPI_KEY`

Free tier: 100 requests/day (developer plan).

### CoinGecko (Optional — Crypto Prices)

1. Go to [coingecko.com/en/api](https://www.coingecko.com/en/api)
2. Sign up → **Demo API Key**
3. Copy → `COINGECKO_API_KEY`

The crypto tool works without a key but with lower rate limits.

---

## 8. Environment Configuration

Open `.env` in your editor and fill in your values:

```bash
# Minimum required to run TILLU
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

REDIS_URL=redis://default:password@your-endpoint.upstash.io:6379

GROQ_API_KEY=gsk_your_groq_key
```

### Full recommended configuration

```bash
# ── Core (Required) ──────────────────────────────────────────
SUPABASE_URL=https://abcdefgh.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret

REDIS_URL=redis://default:password@us1-abc.upstash.io:6379
UPSTASH_REDIS_REST_URL=https://us1-abc.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token

GROQ_API_KEY=gsk_your_key

# ── Recommended ───────────────────────────────────────────────
HF_TOKEN=hf_your_token
CEREBRAS_API_KEY=your_cerebras_key
GOOGLE_API_KEY=AIzaSy_your_key
BRAVE_API_KEY=BSA_your_key
NEWSAPI_KEY=your_newsapi_key
COINGECKO_API_KEY=CG-your_key

# ── App Settings ──────────────────────────────────────────────
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO
SECRET_KEY=change-this-to-a-random-string-in-production
CORS_ORIGINS=http://localhost:3000

# ── Services ──────────────────────────────────────────────────
SEARXNG_URL=http://localhost:8080
PLAYWRIGHT_SERVICE_URL=http://localhost:3001
```

> **Security:** Never commit `.env` to git. It's already in `.gitignore`.

---

## 9. Run Locally

Running locally is the fastest way to test TILLU. You need two terminals.

### Terminal 1 — Gateway

```bash
# Activate virtual environment
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows

# Start the API gateway
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO     Starting TILLU Gateway...
INFO     Redis connected
INFO     Supabase client initialized
INFO     All chains registered
INFO     TILLU Gateway started successfully
INFO     Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2 — Daemon

```bash
source venv/bin/activate

# Start the background daemon
python -m daemon.core
```

Expected output:
```
INFO     Starting TILLU Daemon...
INFO     Started loop: heartbeat
INFO     Started loop: financial_watcher
INFO     Started loop: web_change_detector
...
INFO     Daemon running with 11 active loops
```

### Verify it's working

Open your browser:
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Readiness:** http://localhost:8000/ready

### Send your first message

```bash
curl -X POST http://localhost:8000/api/v1/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-token" \
  -d '{"type": "text", "text": "Hello TILLU!"}'
```

---

## 10. Run with Docker

Docker Compose starts the full stack: Gateway, Daemon, Redis, SearXNG, and n8n.

### Step 1 — Build and start

```bash
docker compose up --build
```

This starts:
| Service | Port | Description |
|---------|------|-------------|
| `gateway` | 8000 | TILLU API |
| `daemon` | — | Background loops |
| `redis` | 6379 | Cache + pub/sub |
| `searxng` | 8080 | Private search engine |
| `n8n` | 5678 | Workflow automation |

### Step 2 — Run in background

```bash
docker compose up -d
```

### Step 3 — View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f gateway
docker compose logs -f daemon
```

### Step 4 — Stop

```bash
docker compose down
```

### Environment variables with Docker

Docker Compose reads from your `.env` file automatically. Make sure it's filled in before running.

---

## 11. Deploy to Render (Production)

Render hosts TILLU for free with always-on services.

### Step 1 — Push to GitHub

```bash
git add .
git commit -m "Initial TILLU setup"
git push origin main
```

### Step 2 — Create Render account

Go to [render.com](https://render.com) and sign up with GitHub.

### Step 3 — Deploy using Blueprint

1. In Render dashboard, click **New → Blueprint**
2. Connect your GitHub repository
3. Render will detect `deployments/render/render.yaml`
4. Click **Apply**

This creates 5 services automatically:
- `tillu-gateway` — Web service (FastAPI)
- `tillu-engine` — Web service (n8n)
- `tillu-daemon` — Worker (background loops)
- `tillu-search` — Web service (SearXNG)
- `tillu-scraper` — Web service (Playwright)

### Step 4 — Set environment variables

For each service, go to **Environment** and add your secrets:

**tillu-gateway** (required):
```
SUPABASE_URL          = https://your-project.supabase.co
SUPABASE_KEY          = your-anon-key
SUPABASE_SERVICE_KEY  = your-service-role-key
REDIS_URL             = redis://default:pass@your.upstash.io:6379
GROQ_API_KEY          = gsk_your_key
HF_TOKEN              = hf_your_token
APP_ENV               = production
DEBUG                 = false
```

**tillu-daemon** (required):
```
SUPABASE_URL          = (same as gateway)
SUPABASE_SERVICE_KEY  = (same as gateway)
REDIS_URL             = (same as gateway)
GROQ_API_KEY          = (same as gateway)
APP_ENV               = production
```

### Step 5 — Deploy

Click **Manual Deploy → Deploy latest commit** for each service.

### Step 6 — Get your gateway URL

After deployment, your gateway URL will be:
```
https://tillu-gateway.onrender.com
```

Test it:
```bash
curl https://tillu-gateway.onrender.com/health
```

---

## 12. Deploy Hugging Face Embedding Space

The HF Space provides a hosted embedding API — useful when you want to offload embedding generation from the main server.

### Step 1 — Create a Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click **Create new Space**
3. Name: `tillu-embeddings`
4. SDK: **Gradio**
5. Hardware: **CPU Basic** (free)
6. Visibility: **Private**

### Step 2 — Upload the space file

Upload `deployments/huggingface/embedding-space.py` as `app.py` in your Space.

Also create a `requirements.txt` in the Space:
```
sentence-transformers==2.2.2
gradio==4.0.0
numpy==1.26.3
```

### Step 3 — Update your .env

Once the Space is running, you can use it as your embedding endpoint:
```bash
HF_INFERENCE_API_URL=https://your-username-tillu-embeddings.hf.space
```

> **Note:** The default HF Inference API (`https://api-inference.huggingface.co`) works fine with just `HF_TOKEN`. The Space is only needed if you want dedicated compute.

---

## 13. n8n Workflow Setup

n8n handles scheduled intelligence workflows (morning briefs, news cycles, etc.).

### Step 1 — Access n8n

- **Local:** http://localhost:5678
- **Render:** https://tillu-engine.onrender.com

Default credentials (change these!):
- Username: `admin`
- Password: `password`

### Step 2 — Import workflows

1. In n8n, go to **Workflows → Import from File**
2. Import `n8n/workflows/message-router.json` (WF-01)
3. Import `n8n/workflows/morning-intelligence-brief.json` (WF-02)

### Step 3 — Configure credentials

In each workflow, update the HTTP Request nodes to point to your gateway:
```
https://tillu-gateway.onrender.com/api/v1/message
```

Add your Bearer token in the Authorization header.

### Step 4 — Activate workflows

Toggle each workflow to **Active** to enable scheduled execution.

---

## 14. Keepalive Configuration

Render's free tier sleeps after 15 minutes of inactivity. TILLU uses a keepalive ring to prevent this.

### Option A — Render Cron Jobs (already in render.yaml)

The `render.yaml` blueprint includes cron jobs that ping each service every 5–10 minutes. These activate automatically when you deploy.

### Option B — UptimeRobot (recommended backup)

1. Go to [uptimerobot.com](https://uptimerobot.com) → Free account
2. **Add New Monitor**:
   - Type: HTTP(s)
   - URL: `https://tillu-gateway.onrender.com/health`
   - Interval: **5 minutes**
3. Repeat for `tillu-engine` and `tillu-search`

### Option C — GitHub Actions

Create `.github/workflows/keepalive.yml`:

```yaml
name: TILLU Keepalive
on:
  schedule:
    - cron: '*/10 * * * *'  # Every 10 minutes
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping Gateway
        run: curl -f https://tillu-gateway.onrender.com/health
      - name: Ping Search
        run: curl -f https://tillu-search.onrender.com/healthz
```

### Option D — Cloudflare Workers (most reliable)

1. Go to [workers.cloudflare.com](https://workers.cloudflare.com)
2. Create a new Worker with this code:

```javascript
export default {
  async scheduled(event, env, ctx) {
    await fetch('https://tillu-gateway.onrender.com/health');
    await fetch('https://tillu-search.onrender.com/healthz');
  }
};
```

3. Set a cron trigger: `*/5 * * * *`

---

## 15. Verify Everything Works

Run through this checklist after setup.

### Health checks

```bash
# Basic health
curl http://localhost:8000/health

# Readiness (checks DB + Redis)
curl http://localhost:8000/ready

# Liveness
curl http://localhost:8000/live
```

Expected response for `/health`:
```json
{"status": "healthy", "timestamp": 1234567890}
```

Expected response for `/ready`:
```json
{
  "status": "ready",
  "checks": {
    "database": "healthy",
    "cache": "healthy"
  }
}
```

### Send a test message

```bash
curl -X POST http://localhost:8000/api/v1/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any-token-works-in-dev" \
  -d '{"type": "text", "text": "What can you do?"}'
```

Expected: JSON response with `response.content` containing TILLU's reply.

### Test memory search

```bash
# Store a memory
curl -X POST "http://localhost:8000/api/v1/memory/store?content=I+prefer+dark+mode&content_type=preference" \
  -H "Authorization: Bearer any-token"

# Search for it
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer any-token" \
  -d '{"query": "my UI preferences", "limit": 5}'
```

### Test SSE stream

```bash
curl -N http://localhost:8000/api/v1/stream \
  -H "Authorization: Bearer any-token" \
  -H "Accept: text/event-stream"
```

You should see:
```
event: connected
data: {"message": "Connected to TILLU event stream", "user_id": "test-user-id"}
```

### Check Prometheus metrics

```bash
curl http://localhost:8000/metrics
```

### Run the test suite

```bash
pytest tests/ -v
```

### Check daemon loops

```bash
# If running with Docker
docker compose logs daemon | grep "Running loop"
```

You should see each loop executing on its schedule.

---

## 16. Troubleshooting

### Gateway won't start

**Error:** `SUPABASE_URL` not set
```
pydantic_settings.exceptions.SettingsError: field required
```
**Fix:** Make sure `.env` exists and has `SUPABASE_URL` and `SUPABASE_KEY` set.

---

**Error:** Redis connection refused
```
redis.exceptions.ConnectionError: Error connecting to localhost:6379
```
**Fix:** Start Redis first:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```
Or set `REDIS_URL` to your Upstash URL.

---

**Error:** Supabase table not found
```
postgrest.exceptions.APIError: relation "user_profile" does not exist
```
**Fix:** Run `supabase/schema.sql` in your Supabase SQL Editor.

---

### Chains not working

**Error:** `GROQ_API_KEY not configured`
**Fix:** Add `GROQ_API_KEY` to your `.env` file.

---

**Error:** Cerebras chain falls back to Groq
**Cause:** `CEREBRAS_API_KEY` not set — this is expected. Groq is the fallback.

---

### Embeddings not generating

**Symptom:** Semantic search returns empty results
**Cause:** `HF_TOKEN` not set or HF API rate limited

**Fix 1:** Add `HF_TOKEN` to `.env`

**Fix 2:** TILLU will fall back to local sentence-transformers automatically. This requires ~500MB RAM for the model. If you're on a low-memory machine, set:
```bash
HF_TOKEN=hf_your_token  # Use the API instead
```

---

### Docker build fails

**Error:** `torch` installation timeout
**Fix:** torch is large (~2GB). Increase Docker build timeout or use a pre-built image:
```bash
# Build with no cache and extended timeout
DOCKER_BUILDKIT=1 docker compose build --no-cache
```

---

### Render service keeps sleeping

**Symptom:** First request after idle takes 30+ seconds
**Fix:** Set up keepalive (see [Section 14](#14-keepalive-configuration))

---

### n8n workflows not triggering

**Symptom:** Morning brief never arrives
**Fix:**
1. Check workflow is **Active** (toggle in n8n)
2. Check the gateway URL in HTTP Request nodes
3. Check n8n logs: `docker compose logs n8n`

---

### pgvector similarity search returns nothing

**Symptom:** Memory search always returns 0 results
**Cause:** Embeddings not being generated (HF token missing) or similarity threshold too high

**Fix:**
```bash
# Lower the threshold in your search request
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer token" \
  -d '{"query": "test", "limit": 10, "similarity_threshold": 0.3}'
```

---

## 17. Cost Summary

TILLU is engineered to run entirely on free tiers.

| Service | Free Tier | TILLU Usage | Status |
|---------|-----------|-------------|--------|
| **Supabase** | 500MB storage, 500k requests/month | ~400MB, ~200k req | ✅ Safe |
| **Upstash Redis** | 10,000 ops/day | ~8,000 ops/day | ✅ Safe |
| **Groq** | 14,400 tokens/min | ~5,000 tokens/min | ✅ Safe |
| **Cerebras** | ~500 requests/day | ~200 req/day | ✅ Safe |
| **Hugging Face** | Rate limited | <1,000 req/day | ✅ Safe |
| **Render** | 5 free services | 5 services used | ✅ Safe |
| **NewsAPI** | 100 req/day | ~50 req/day | ✅ Safe |
| **CoinGecko** | Unlimited (demo) | ~100 req/day | ✅ Safe |
| **Brave Search** | 2,000 req/month | ~500 req/month | ✅ Safe |
| **UptimeRobot** | 50 monitors | 3 monitors | ✅ Safe |

**Total monthly cost: $0**

---

## Quick Reference

### Start commands

```bash
# Local development
uvicorn app.main:app --reload          # Gateway
python -m daemon.core                  # Daemon

# Docker
docker compose up -d                   # Full stack
docker compose logs -f gateway         # Watch logs
docker compose down                    # Stop

# Tests
pytest tests/ -v                       # Run all tests
pytest tests/ -v -m unit               # Unit tests only
pytest tests/ -v -m "not slow"         # Skip slow tests
```

### Key URLs

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Interactive API docs (Swagger) |
| `http://localhost:8000/redoc` | API docs (ReDoc) |
| `http://localhost:8000/health` | Health check |
| `http://localhost:8000/metrics` | Prometheus metrics |
| `http://localhost:8080` | SearXNG search UI |
| `http://localhost:5678` | n8n workflow editor |

### Minimum .env

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
REDIS_URL=redis://localhost:6379
GROQ_API_KEY=gsk_your_key
```

---

*Built to run forever. Set it up once, let it run.*
