# TILLU Architecture Documentation

## System Overview

TILLU is a three-process, event-driven personal AI backend designed for zero-cost perpetual operation.

## Three Concurrent Processes

### Process 1: Gateway (tillu-gateway)

**Role**: Single public face of TILLU  
**Technology**: FastAPI + Uvicorn (4 workers) + Gunicorn  
**State**: Stateless - all state in Redis and Supabase

**Responsibilities**:
- Receive all inbound client requests
- Authenticate and validate
- Assemble context from Supabase + Redis
- Route to appropriate LangChain chain
- Return structured response
- Push queued events to connected clients via SSE/WebSocket

**API Endpoints**:
- `POST /api/v1/message` - Process any input
- `GET /api/v1/stream` - SSE event stream
- `POST /api/v1/memory/search` - Semantic memory query
- `POST /api/v1/register` - Client registration
- `GET /api/v1/health` - System health status
- `GET /api/v1/analytics` - Usage metrics

### Process 2: Engine (tillu-engine)

**Role**: Scheduled intelligence production  
**Technology**: n8n self-hosted (Docker) + LangChain Python workers  
**Critical Design**: Engine never delivers directly - only publishes to Redis

**Responsibilities**:
- Execute all n8n cron-triggered workflows
- Run background LangChain chains
- Consume external data sources continuously
- Generate proactive intelligence packets
- Publish events to Redis pub/sub

**18 Scheduled Workflows**:
1. WF-01: Message Router (webhook-triggered)
2. WF-02: Morning Intelligence Brief (daily 07:00)
3. WF-03: News Intelligence Cycle (every 30 min)
4. WF-04: Research Orchestrator
5. WF-05: Financial Intelligence (every 15 min)
6. WF-06: Email Intelligence
7. WF-07: Calendar Intelligence
8. WF-08: Task Accountability
9. WF-09: Memory Consolidation (daily 00:00)
10. WF-10: Weekly Life Analytics (Sunday 20:00)
11. WF-11: Pattern Recognition Cycle (every 6 hours)
12. WF-12: Self-Improvement Audit
13. WF-13: Free Tier Governance (daily 23:00)
14. WF-14: Web Monitor Cycle (every 30 min)
15. WF-15: Relationship Intelligence (daily 09:00)
16. WF-16: Knowledge Base Maintenance
17. WF-17: Context Pre-Computation (hourly)
18. WF-18: System Health Guardian (every 5 min)

### Process 3: Daemon (tillu-daemon)

**Role**: Always-watching ambient intelligence  
**Technology**: Python asyncio - pure async loops  
**Design**: Infinite loops, independent, self-restarting

**11 Concurrent Loops**:

| Loop | Interval | Purpose |
|------|----------|---------|
| 1. Heartbeat | 60s | System health ping |
| 2. Financial Watcher | 15m | Asset price monitoring |
| 3. Web Change Detector | 30m | URL change detection |
| 4. News Urgency Scanner | 10m | News escalation |
| 5. Pattern Recognition | 1h | Behavioral analysis |
| 6. Context Pre-Computer | 1h | Context caching |
| 7. Rate Limit Tracker | 5m | API quota management |
| 8. Free Tier Governor | 1h | Resource governance |
| 9. Goal Probability | 6h | Completion forecasting |
| 10. Emotion Trend | 30m | Emotional tracking |
| 11. Relationship Monitor | 6h | Birthday/check tracking |

## Inter-Process Communication

All processes communicate **exclusively via Redis Pub/Sub**:

```
Channels:
tillu:events:urgent      urgency 8-10, immediate delivery
tillu:events:normal       urgency 4-7, batched delivery
tillu:events:low          urgency 1-3, daily digest
tillu:commands:engine     gateway → engine directives
tillu:commands:daemon     gateway → daemon directives
tillu:system:health       all processes publish heartbeat
tillu:analytics           all processes publish metrics
```

**No process imports another. No direct function calls.**

Total decoupling = any process can restart without breaking others.

## Cognitive Architecture

### Context Assembler (7 Tiers)

Every chain execution is preceded by context assembly:

```
TIER 1 — Identity (< 5ms, Redis cache)
→ user_profile loaded
→ personality_params computed
→ active_hours classification

TIER 2 — Temporal (< 2ms)
→ current datetime + timezone
→ behavioral pattern for this hour/day
→ DND window check

TIER 3 — Emotional State (< 10ms, Redis cache)
→ 7-day emotion average
→ today's trajectory
→ current stress estimate

TIER 4 — Immediate Memory (< 20ms, Supabase)
→ ConversationBufferWindowMemory: last 20 turns
→ today's interaction summary

TIER 5 — Semantic Memory (< 50ms, pgvector)
→ embed input query
→ cosine similarity search
→ top 8 conversations, 5 knowledge, 3 research

TIER 6 — Situational (< 15ms, Supabase + Redis)
→ today's tasks + approaching deadlines
→ active goals + probability scores
→ pending proactive events queued

TIER 7 — World State (< 10ms, Redis cache)
→ breaking news last 2 hours
→ financial movements >2%
→ pre-computed morning context
```

**Target assembly time: < 120ms**

### Chain Registry (10 Chains)

| # | Chain | Type | Model | Trigger |
|---|-------|------|-------|---------|
| 01 | Conversational | ConversationChain | Groq 70B/8B | small_talk |
| 02 | Research | LangGraph | Cerebras/Groq | research_request |
| 03 | ReAct Agent | ReAct Agent | Gemini Pro | action_required |
| 04 | Analysis | LLMChain | Cerebras 70B | pattern_query |
| 05 | Intelligence Compiler | MapReduce | Groq 70B | Scheduled |
| 06 | Empathy | ConversationChain | Groq 70B | distress |
| 07 | Self-Critique | LLMChain | Groq 8B | After every response |
| 08 | Memory Consolidation | Sequential | Groq 70B | Daily 00:00 |
| 09 | Personality Evolution | LLMChain | Groq 70B | Weekly Sunday 22:00 |
| 10 | Ambient Monitoring | LLMChain | Groq 8B | Every 30 min |

### LangChain Memory Stack

```
CombinedMemory (wraps all three):
│
├── ConversationBufferWindowMemory
│   Window: last 20 messages
│   Purpose: Immediate conversation coherence
│
├── VectorStoreRetrieverMemory
│   Store: Supabase pgvector
│   Retriever: similarity threshold 0.75
│   Purpose: Long-term semantic recall
│
└── ConversationSummaryMemory
    Model: Groq Llama 3.1 8B
    Purpose: Compressed history
    Trigger: Conversation > 40 turns
```

## Data Layer

### Supabase Schema (12 Tables)

1. **user_profile** - Living user model + personality params
2. **interactions** - Full interaction log with quality scores
3. **knowledge_base** - Semantic store with pgvector embeddings
4. **news_articles** - Processed news with urgency scores
5. **event_queue** - Proactive events waiting for delivery
6. **research_sessions** - Full research records
7. **tasks_goals** - Tasks/goals with probability scoring
8. **emotion_log** - Timestamped emotional states
9. **financial_tracking** - Asset tracking with price history
10. **web_monitors** - URL watchers with state
11. **people_knowledge** - Relationship intelligence
12. **system_analytics** - Per-hour operational metrics

### Vector Store (pgvector)

- **knowledge_base.embedding** - 768-dim vectors
- **news_articles.embedding** - 768-dim vectors
- **research_sessions.embedding** - 768-dim vectors
- **people_knowledge.embedding** - 768-dim vectors

Similarity search functions:
- `search_knowledge(query_embedding, user_id, threshold, limit)`
- `search_news(query_embedding, user_id, threshold, limit)`

## LLM Routing System

### Provider Registry

| Provider | Models | Free Limit | Strength |
|----------|--------|------------|----------|
| Groq | Llama 3.1 8B/70B | 14.4k tokens/min | Speed |
| Cerebras | Llama 3.3 70B | ~500 req/day | Deep reasoning |
| OpenRouter | 100+ models | 200 req/day | Variety |
| Google Gemini | Pro/Flash | 1500 req/day | Multimodal |
| HF Inference | All public | Rate limited | Specialized |

### Routing Decision Matrix

```
Input factors:
→ intent_class
→ estimated_tokens
→ requires_speed (urgency flag)
→ requires_depth (complexity score)
→ provider_remaining_capacity

Decision:
quick_chat + tokens < 500     → Groq 8B
deep_reasoning / analysis    → Cerebras 70B
tool_use / multi_step         → Gemini Pro
coding                        → OpenRouter → DeepSeek Coder V2
creative / long_form          → Groq 70B
multimodal (image input)      → Gemini Flash
summarization                 → Cohere Command R+

primary_provider.remaining < 20%  → rotate to next
all_primary_providers < 10%     → OpenRouter free models
```

## Free Tier Governance

### Keepalive Ring

```
Render sleeps after 15min inactivity → UNACCEPTABLE

SOLUTION: Circular keepalive
┌──────────┐ pings ┌──────────┐ pings ┌──────────┐
│ gateway  │ ────► │ engine   │ ────► │ daemon   │
│          │ ◄──── │          │ ◄──── │          │
└──────────┘       └──────────┘       └──────────┘
     ▲                                    │
     └────────────────────────────────────┘

EXTERNAL REDUNDANCY:
- UptimeRobot free → /health ping every 5 min
- cron-job.org free → backup ping every 10 min
- Cloudflare Worker → cron trigger every 5 min
- GitHub Actions → scheduled ping every 10 min

RESULT: All services perpetually warm. Zero cold starts.
```

### Cost Budget (Monthly)

| Service | Free Tier | Projected Usage | Status |
|---------|-----------|-----------------|--------|
| Supabase | 500MB | 400MB | OK |
| Upstash | 10k ops/day | 8k ops/day | OK |
| Groq | 14.4k/min | ~5k/min | OK |
| Cerebras | ~500/day | ~200/day | OK |
| HF Inference | Rate limited | <1000/day | OK |

## Security

### Authentication

- Bearer token authentication (Supabase JWT)
- Row Level Security (RLS) on all tables
- Service role for backend processes

### Data Privacy

- All data in user's Supabase project
- No data sharing with third parties
- Self-hosted where possible (SearXNG, Playwright)

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTS                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│  │ WhatsApp   │  │   Web App  │  │   Mobile   │               │
│  │ (Baileys)  │  │   (React)  │  │  (iOS/And) │               │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘               │
└─────────┼──────────────┼──────────────┼────────────────────────┘
          │              │              │
          └──────────────┼──────────────┘
                         │ HTTPS + Bearer Auth
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RENDER PLATFORM                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                     TILLU GATEWAY                          │ │
│  │                    FastAPI + Uvicorn                       │ │
│  │                      (always-on)                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │ TILLU ENGINE │   │ TILLU DAEMON │   │ TILLU SEARCH │      │
│  │    (n8n)     │   │  (11 loops)  │   │  (SearXNG)   │      │
│  └──────────────┘   └──────────────┘   └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
  ┌──────────────┐ ┌──────────┐  ┌─────────────┐
  │   SUPABASE   │ │  UPSTASH │  │  HF Spaces  │
  │ PostgreSQL   │ │  Redis   │  │ Embeddings  │
  │  + pgvector  │ │ Pub/Sub  │  │  Whisper    │
  └──────────────┘ └──────────┘  └─────────────┘
```

## Monitoring & Observability

### Metrics

- Prometheus metrics at `/metrics`
- Per-chain latency tracking
- API usage per provider
- Event queue depths
- Error rates

### Logging

- Structured logging with structlog
- Request ID correlation
- User ID correlation
- Chain execution logging

### Health Checks

- `/health` - Basic health
- `/ready` - Readiness probe (K8s)
- `/live` - Liveness probe (K8s)

## Roadmap

### Phase 1: Foundation ✓
- Supabase schema deployed
- FastAPI gateway operational
- Basic conversational chain working
- Context assembler (tiers 1-3)

### Phase 2: Memory (Next)
- pgvector setup
- Embedding pipeline (HF Inference API)
- Full context assembler (all 7 tiers)
- CombinedMemory integration

### Phase 3: Intelligence
- Transformer pipeline (emotion, intent, stress, NER, BART)
- All 10 chains implemented
- LangGraph research agent
- Tool registry (32 tools)

### Phase 4: Autonomy
- n8n all 18 workflows
- Daemon all 11 loops live
- Redis pub/sub event system
- SSE/WebSocket delivery

### Phase 5: Real World
- SearXNG deployed
- All news sources integrated
- Financial monitoring live
- Web change monitor live

### Phase 6: Adaptation
- Personality evolution chain
- Self-critique chain
- Weekly analytics workflow
- Behavioral pattern engine

### Phase 7: Production
- LangSmith tracing for all chains
- Full error handling
- Rate limit exhaustion handling
- Load testing complete
