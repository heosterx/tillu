# TILLU Hosting Plan

## Executive Summary

TILLU is engineered to run **entirely on free tiers** with zero monthly cost. The system is distributed across multiple cloud providers to maximize uptime and avoid vendor lock-in.

**Total Monthly Cost: $0**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    TILLU HOSTING STACK                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ GATEWAY (FastAPI) — Render.com                           │   │
│  │ • Web service (free tier)                                │   │
│  │ • Always-on with keepalive                               │   │
│  │ • URL: https://tillu-gateway.onrender.com                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ DAEMON (Python) — Render.com                             │   │
│  │ • Worker service (free tier)                             │   │
│  │ • 11 background loops                                    │   │
│  │ • Runs continuously                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ WEBSEARCH (Docker) — Render.com                          │   │
│  │ • Web service (free tier)                                │   │
│  │ • Brave API + DuckDuckGo fallback                        │   │
│  │ • URL: https://tillu-websearch.onrender.com              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ENGINE (n8n) — Hugging Face Spaces                       │   │
│  │ • Free tier Space                                        │   │
│  │ • Scheduled workflows                                    │   │
│  │ • URL: https://huggingface.co/spaces/tillu-AI/tillu-engine │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ DATABASE — Supabase                                      │   │
│  │ • PostgreSQL + pgvector                                  │   │
│  │ • Free tier: 500MB storage, 500k requests/month          │   │
│  │ • URL: https://your-project.supabase.co                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ CACHE — Upstash Redis                                    │   │
│  │ • Serverless Redis                                       │   │
│  │ • Free tier: 10k ops/day                                 │   │
│  │ • Pub/Sub for inter-process communication                │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ LLM PROVIDERS                                            │   │
│  │ • Groq (primary) — 14.4k tokens/min free                 │   │
│  │ • Cerebras (fallback) — ~500 req/day free                │   │
│  │ • Google AI Studio (ReAct) — free tier                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ KEEPALIVE RING                                           │   │
│  │ • Render cron jobs (built-in)                            │   │
│  │ • Pings every 5-10 minutes                               │   │
│  │ • Prevents free tier sleep                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Service Breakdown

### 1. Render.com (Primary Hosting)

**What:** FastAPI gateway, daemon worker, websearch service
**Cost:** $0/month (free tier)
**Limits:** 
- 5 free services per account
- 750 hours/month per service
- 100GB/month bandwidth
- Auto-sleep after 15 min inactivity (mitigated by keepalive)

**TILLU Usage:**
- `tillu-gateway` (web service) — 24/7 API
- `tillu-daemon` (worker service) — 24/7 background loops
- `tillu-websearch` (web service) — 24/7 search API
- 2 cron jobs for keepalive

**Why Render:**
- Free tier is generous (750 hours = 31 days)
- Supports both web services and workers
- Built-in cron jobs for keepalive
- Easy GitHub integration
- No credit card required for free tier

**Deployment:**
```bash
# Push to GitHub
git push origin main

# Render auto-deploys via render.yaml blueprint
# Services start automatically
```

**Monitoring:**
- Dashboard: https://dashboard.render.com
- Logs: Available in Render dashboard
- Health: `/health` endpoint

---

### 2. Supabase (Database)

**What:** PostgreSQL database with pgvector extension
**Cost:** $0/month (free tier)
**Limits:**
- 500MB storage
- 500,000 requests/month
- 2GB bandwidth/month
- 1 project

**TILLU Usage:**
- 13 tables (interactions, knowledge_base, news_articles, etc.)
- ~400MB storage (estimated)
- ~200k requests/month (estimated)

**Why Supabase:**
- pgvector for semantic search
- Row-level security (RLS) for multi-user
- Real-time subscriptions
- Built-in auth (JWT)
- Free tier is sufficient for personal use

**Setup:**
```bash
# 1. Create project at supabase.com
# 2. Enable pgvector extension
# 3. Run supabase/schema.sql in SQL Editor
# 4. Copy credentials to .env
```

**Monitoring:**
- Dashboard: https://app.supabase.com
- Query performance: SQL Editor
- Storage usage: Settings → Usage

---

### 3. Upstash Redis (Cache + Pub/Sub)

**What:** Serverless Redis for caching and inter-process communication
**Cost:** $0/month (free tier)
**Limits:**
- 10,000 operations/day
- 1 database
- 256MB storage
- 1 concurrent connection

**TILLU Usage:**
- ~8,000 ops/day (estimated)
- Pub/Sub for gateway ↔ daemon communication
- Session caching
- Rate limit tracking

**Why Upstash:**
- Serverless (no infrastructure to manage)
- REST API + native Redis protocol
- Perfect for free-tier architecture
- Automatic backups

**Setup:**
```bash
# 1. Create database at upstash.com
# 2. Copy REDIS_URL to .env
# 3. Optional: Use REST API for serverless functions
```

**Monitoring:**
- Dashboard: https://console.upstash.com
- Operations/day: Real-time graph
- Latency: Performance metrics

---

### 4. Groq API (Primary LLM)

**What:** Fast, free LLM inference
**Cost:** $0/month (free tier)
**Limits:**
- 14,400 tokens/minute
- 500 requests/day (soft limit)
- Llama 3.1 70B/8B models

**TILLU Usage:**
- ~5,000 tokens/min (estimated)
- Conversational chain (primary)
- Fallback for other chains

**Why Groq:**
- Fastest inference (50-100ms)
- Free tier is generous
- No credit card required
- Excellent for personal AI

**Setup:**
```bash
# 1. Sign up at console.groq.com
# 2. Create API key
# 3. Add to .env: GROQ_API_KEY=gsk_...
```

**Monitoring:**
- Dashboard: https://console.groq.com
- Token usage: Real-time
- Rate limits: API status page

---

### 5. Cerebras API (Deep Analysis)

**What:** Fast, accurate LLM for complex reasoning
**Cost:** $0/month (free tier)
**Limits:**
- ~500 requests/day
- Llama 3.1 70B model
- 200k tokens/day

**TILLU Usage:**
- ~200 requests/day (estimated)
- Analysis chain (deep reasoning)
- Fallback to Groq if rate limited

**Why Cerebras:**
- Excellent for complex analysis
- Free tier is sufficient
- Faster than many paid alternatives

**Setup:**
```bash
# 1. Sign up at cloud.cerebras.ai
# 2. Request API access
# 3. Create API key
# 4. Add to .env: CEREBRAS_API_KEY=...
```

---

### 6. Google AI Studio (ReAct Agent)

**What:** Gemini API for tool-using agent
**Cost:** $0/month (free tier)
**Limits:**
- 60 requests/minute
- 1,500 requests/day
- Gemini 1.5 Flash model

**TILLU Usage:**
- ~100 requests/day (estimated)
- ReAct agent chain (tool calling)
- Calendar + Gmail integration

**Why Google:**
- Excellent tool-calling capabilities
- Free tier is generous
- Gemini 1.5 is very capable

**Setup:**
```bash
# 1. Go to aistudio.google.com
# 2. Click "Get API Key"
# 3. Create new API key
# 4. Add to .env: GOOGLE_API_KEY=...
```

---

### 7. Hugging Face (Embeddings + NLP)

**What:** Embeddings, transformers, and hosted Spaces
**Cost:** $0/month (free tier)
**Limits:**
- Rate limited (varies by model)
- 1 free Space per account
- 50GB storage per Space

**TILLU Usage:**
- ~1,000 requests/day (estimated)
- Embeddings for semantic search
- Emotion detection, intent classification
- Optional: Hosted embedding Space

**Why Hugging Face:**
- Best open-source models
- Free tier is sufficient
- Spaces for hosting services

**Setup:**
```bash
# 1. Sign up at huggingface.co
# 2. Create access token
# 3. Add to .env: HF_TOKEN=hf_...
# 4. Optional: Create Space for n8n
```

---

### 8. Brave Search API (Web Search)

**What:** Privacy-focused web search
**Cost:** $0/month (free tier)
**Limits:**
- 2,000 requests/month
- Brave Search results

**TILLU Usage:**
- ~500 requests/month (estimated)
- Web search for research chain
- Fallback to DuckDuckGo if rate limited

**Why Brave:**
- Privacy-focused
- Free tier is sufficient
- Good search quality

**Setup:**
```bash
# 1. Sign up at api.search.brave.com
# 2. Create API key
# 3. Add to .env: BRAVE_API_KEY=...
```

---

### 9. NewsAPI (News Intelligence)

**What:** News aggregation API
**Cost:** $0/month (free tier)
**Limits:**
- 100 requests/day
- Developer plan

**TILLU Usage:**
- ~50 requests/day (estimated)
- News scanning loop
- Morning brief

**Why NewsAPI:**
- Comprehensive news coverage
- Free tier is sufficient
- Easy integration

**Setup:**
```bash
# 1. Sign up at newsapi.org
# 2. Get API key
# 3. Add to .env: NEWSAPI_KEY=...
```

---

### 10. CoinGecko API (Crypto Prices)

**What:** Cryptocurrency price data
**Cost:** $0/month (free tier)
**Limits:**
- Unlimited (demo API)
- Rate limited to ~10 calls/second

**TILLU Usage:**
- ~100 requests/day (estimated)
- Financial monitoring loop
- Crypto price alerts

**Why CoinGecko:**
- Unlimited free tier
- No API key required (optional)
- Comprehensive crypto data

---

## Keepalive Strategy

Render's free tier sleeps after 15 minutes of inactivity. TILLU uses a multi-layered keepalive strategy:

### Layer 1: Render Cron Jobs (Primary)

Built into `render.yaml`:
```yaml
jobs:
  - name: keepalive-gateway
    schedule: "*/5 * * * *"  # Every 5 minutes
    command: curl https://tillu-gateway.onrender.com/health

  - name: keepalive-websearch
    schedule: "*/10 * * * *"  # Every 10 minutes
    command: curl https://tillu-websearch.onrender.com/health
```

**Pros:** Built-in, no external dependencies
**Cons:** Limited to Render services

### Layer 2: UptimeRobot (Backup)

Optional backup keepalive:
```
Service: UptimeRobot (free tier)
URL: https://tillu-gateway.onrender.com/health
Interval: 5 minutes
Monitors: 3 (gateway, websearch, engine)
```

**Pros:** Independent of Render
**Cons:** Requires external service

### Layer 3: GitHub Actions (Tertiary)

Optional GitHub Actions workflow:
```yaml
name: TILLU Keepalive
on:
  schedule:
    - cron: '*/10 * * * *'
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -f https://tillu-gateway.onrender.com/health
```

**Pros:** Free with GitHub
**Cons:** Requires GitHub account

### Layer 4: Daemon Internal Loops

The daemon itself acts as a keepalive:
- Heartbeat loop (60s)
- Financial watcher (15m)
- News scanner (10m)
- Web change detector (30m)

These loops continuously hit the database and cache, keeping the system warm.

---

## Cost Breakdown

| Service | Free Tier | TILLU Usage | Status | Cost |
|---------|-----------|-------------|--------|------|
| **Render** | 750h/mo, 5 services | 3 services, 24/7 | ✅ Safe | $0 |
| **Supabase** | 500MB, 500k req/mo | 400MB, 200k req | ✅ Safe | $0 |
| **Upstash Redis** | 10k ops/day | 8k ops/day | ✅ Safe | $0 |
| **Groq** | 14.4k tokens/min | 5k tokens/min | ✅ Safe | $0 |
| **Cerebras** | ~500 req/day | 200 req/day | ✅ Safe | $0 |
| **Google AI** | 1.5k req/day | 100 req/day | ✅ Safe | $0 |
| **Hugging Face** | Rate limited | 1k req/day | ✅ Safe | $0 |
| **Brave Search** | 2k req/month | 500 req/month | ✅ Safe | $0 |
| **NewsAPI** | 100 req/day | 50 req/day | ✅ Safe | $0 |
| **CoinGecko** | Unlimited | 100 req/day | ✅ Safe | $0 |
| **UptimeRobot** | 50 monitors | 3 monitors | ✅ Safe | $0 |
| **GitHub** | Unlimited | 1 repo | ✅ Safe | $0 |
| **Cloudflare** | Unlimited | Optional | ✅ Safe | $0 |
| | | | **TOTAL** | **$0** |

---

## Scaling Path (If Needed)

If TILLU grows beyond free tier limits, here's the upgrade path:

### Phase 1: Paid Tier (Estimated $50-100/month)

| Service | Upgrade | Cost | When |
|---------|---------|------|------|
| Render | Pro tier | $7/service | If >750h/mo |
| Supabase | Pro tier | $25/mo | If >500MB storage |
| Upstash | Pro tier | $20/mo | If >10k ops/day |
| Groq | Paid tier | $0.50/1M tokens | If >14.4k tokens/min |

### Phase 2: Multi-Region (Estimated $100-200/month)

- Deploy to multiple Render regions
- Replicate Supabase to multiple regions
- Use Cloudflare for global CDN

### Phase 3: Enterprise (Estimated $500+/month)

- Dedicated Kubernetes cluster
- Managed PostgreSQL
- Dedicated Redis
- Premium LLM APIs

---

## Deployment Checklist

### Pre-Deployment

- [ ] Create Supabase account and project
- [ ] Create Upstash Redis database
- [ ] Get Groq API key
- [ ] Get Cerebras API key (optional)
- [ ] Get Google AI Studio key (optional)
- [ ] Get Brave Search key (optional)
- [ ] Get NewsAPI key (optional)
- [ ] Create GitHub account and push code
- [ ] Create Render account (link GitHub)
- [ ] Create Hugging Face account (optional)

### Deployment

- [ ] Fill in `.env` with all credentials
- [ ] Run `supabase/schema.sql` in Supabase
- [ ] Push to GitHub
- [ ] Deploy via Render blueprint (`render.yaml`)
- [ ] Set environment variables in Render dashboard
- [ ] Verify all services are running
- [ ] Test `/health` endpoint
- [ ] Test `/api/v1/message` endpoint
- [ ] Set up keepalive (Render cron jobs are automatic)

### Post-Deployment

- [ ] Monitor Render dashboard for errors
- [ ] Check Supabase storage usage
- [ ] Check Upstash operations/day
- [ ] Check Groq token usage
- [ ] Set up monitoring alerts (optional)
- [ ] Document your deployment URLs
- [ ] Share API docs with clients

---

## Monitoring & Alerts

### Key Metrics to Watch

| Metric | Threshold | Action |
|--------|-----------|--------|
| Render uptime | <99% | Check logs, restart service |
| Supabase storage | >400MB | Archive old data |
| Upstash ops/day | >8k | Optimize queries |
| Groq tokens/min | >10k | Reduce context size |
| API response time | >2s | Check database |
| Error rate | >1% | Review logs |

### Monitoring Tools

**Render Dashboard:**
- https://dashboard.render.com
- Real-time logs
- Service status
- Deployment history

**Supabase Dashboard:**
- https://app.supabase.com
- Storage usage
- Request count
- Query performance

**Upstash Dashboard:**
- https://console.upstash.com
- Operations/day graph
- Latency metrics
- Connection status

**Groq Dashboard:**
- https://console.groq.com
- Token usage
- Request count
- Rate limit status

---

## Disaster Recovery

### Backup Strategy

**Database Backups:**
- Supabase auto-backups (daily)
- Manual export: Settings → Backups → Download
- Frequency: Weekly

**Code Backups:**
- GitHub (primary)
- Local git clone
- Frequency: Every commit

**Configuration Backups:**
- `.env` file (keep secure)
- Render environment variables (documented)
- Frequency: After changes

### Recovery Procedures

**If Gateway is Down:**
1. Check Render dashboard for errors
2. Review logs: `Render → tillu-gateway → Logs`
3. Restart service: `Render → tillu-gateway → Manual Deploy`
4. If still down, check Supabase and Redis connectivity

**If Database is Down:**
1. Check Supabase status: https://status.supabase.com
2. Verify credentials in `.env`
3. Test connection: `psql $SUPABASE_URL`
4. If corrupted, restore from backup

**If Redis is Down:**
1. Check Upstash dashboard
2. Verify credentials in `.env`
3. Test connection: `redis-cli -u $REDIS_URL ping`
4. If corrupted, create new database

**If LLM API is Down:**
1. Check provider status page
2. Verify API key is valid
3. Check rate limits
4. Switch to fallback provider

---

## Security Considerations

### Secrets Management

**Never commit secrets to git:**
```bash
# .env is in .gitignore
# But verify:
git check-ignore .env
```

**Render environment variables:**
- Set via Render dashboard (encrypted)
- Never log secrets
- Rotate keys periodically

**Supabase security:**
- Use service role key only on backend
- Use anon key for frontend
- Enable RLS on all tables
- Rotate JWT secret annually

### API Security

**Authentication:**
- All endpoints require Bearer token
- Tokens validated against Supabase JWT
- Rate limiting per user

**Authorization:**
- Row-level security (RLS) on Supabase
- User can only access their own data
- Service role key for admin operations

**Data Protection:**
- HTTPS only (Render + Supabase)
- Encryption at rest (Supabase)
- Encryption in transit (TLS 1.3)

---

## Support & Troubleshooting

### Common Issues

**"Service is sleeping"**
- Render free tier sleeps after 15 min inactivity
- Keepalive cron jobs should prevent this
- Check Render dashboard for cron job status

**"Database connection refused"**
- Check SUPABASE_URL and SUPABASE_KEY
- Verify Supabase project is active
- Check network connectivity

**"Redis connection refused"**
- Check REDIS_URL format
- Verify Upstash database is active
- Check IP whitelist (if applicable)

**"Rate limit exceeded"**
- Check which API is rate limited
- Reduce request frequency
- Switch to fallback provider
- Wait for rate limit reset

### Getting Help

- **Render Support:** https://render.com/support
- **Supabase Docs:** https://supabase.com/docs
- **Upstash Docs:** https://upstash.com/docs
- **Groq Community:** https://console.groq.com/docs
- **GitHub Issues:** Create issue in repository

---

## Conclusion

TILLU is designed to run indefinitely on free tiers with zero cost. The multi-provider architecture ensures:

- **Reliability:** No single point of failure
- **Scalability:** Easy upgrade path if needed
- **Sustainability:** Zero ongoing costs
- **Simplicity:** Minimal infrastructure management

Deploy once, let it run forever.

---

**Last Updated:** May 2026
**Status:** Production Ready
**Cost:** $0/month
