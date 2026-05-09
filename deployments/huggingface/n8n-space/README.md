---
title: TILLU Engine
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: true
license: mit
short_description: TILLU n8n workflow engine — IST timezone, Supabase backend
---

# TILLU Engine — n8n on HuggingFace Spaces

Self-hosted n8n workflow automation engine for the TILLU personal AI system.

- **Timezone**: IST (Asia/Kolkata)
- **Database**: Supabase PostgreSQL (persistent across restarts)
- **Hardware**: CPU Basic — 2 vCPU, 16GB RAM, 50GB disk (free)

## Setup

### 1. Required HF Space Secrets

Go to **Settings → Variables and secrets** and add:

| Secret | Value |
|--------|-------|
| `N8N_ENCRYPTION_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `N8N_BASIC_AUTH_USER` | `admin` |
| `N8N_BASIC_AUTH_PASSWORD` | your strong password |
| `DB_POSTGRESDB_HOST` | `db.dpkmzkyzvmysvzmevhrm.supabase.co` |
| `DB_POSTGRESDB_DATABASE` | `postgres` |
| `DB_POSTGRESDB_USER` | `postgres` |
| `DB_POSTGRESDB_PASSWORD` | your Supabase DB password |
| `TILLU_GATEWAY_URL` | `https://tillu-gateway.onrender.com` |
| `WEBHOOK_URL` | `https://tillu-ai-tillu-engine.hf.space` |

### 2. Create Supabase schema for n8n

Run this in your Supabase SQL editor:
```sql
CREATE SCHEMA IF NOT EXISTS n8n;
```

### 3. Access n8n

Once running, open the Space URL and log in with your `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`.

### 4. Import TILLU workflows

The workflows are pre-copied into the container at `/root/.n8n/workflows/`.
They auto-load on first start. You can also import manually via n8n UI → Settings → Import.

## Workflows included

| ID | Name | Schedule |
|----|------|----------|
| WF-01 | Message Router | Webhook |
| WF-02 | Morning Intelligence Brief | 7:00 AM IST |
| WF-09 | Memory Consolidation | 12:00 AM IST |
| WF-16 | Personality Evolution | Sunday 10:00 PM IST |

## Persistence

Workflows and credentials are stored in **Supabase PostgreSQL** — they survive Space restarts.
The `n8n` schema is created automatically on first run.
