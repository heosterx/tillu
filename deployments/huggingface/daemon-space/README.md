---
title: TILLU Daemon
emoji: 🔄
colorFrom: purple
colorTo: indigo
sdk: docker
pinned: true
license: mit
short_description: TILLU background intelligence — 16 async loops
---

# TILLU Daemon

Always-watching background intelligence for the TILLU AI system.

## What it does

Runs 16 concurrent async loops:

| Loop | Interval | Purpose |
|------|----------|---------|
| Heartbeat | 60s | System health + Redis pub/sub |
| Financial Watcher | 15m | NSE/BSE/crypto price monitoring |
| Web Change Detector | 30m | URL change detection |
| News Urgency Scanner | 10m | Breaking news escalation |
| Pattern Recognition | 1h | Behavioral analysis |
| Context Pre-Computer | 1h | Context caching |
| Rate Limit Tracker | 5m | API quota management |
| Free Tier Governor | 1h | Resource governance |
| Goal Probability | 6h | Completion forecasting |
| Emotion Trend | 30m | Emotional state tracking |
| Relationship Monitor | 6h | Birthday/check-in tracking |
| Email Monitor | 30m | Gmail intelligence |
| Calendar Monitor | 1h | Google Calendar sync |
| Memory Consolidation | 24h | Daily memory consolidation |
| Personality Evolution | 7d | Weekly personality update |
| Ambient Monitoring | 30m | Proactive intelligence |

## Health endpoint

`GET /health` — returns daemon status and active loop count

## Space Secrets required

| Secret | Description |
|--------|-------------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `REDIS_URL` | Upstash Redis URL |
| `GROQ_API_KEY` | Groq API key |
| `HF_TOKEN` | HuggingFace token |
| `SECRET_KEY` | App secret key |
