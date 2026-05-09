# TILLU Backend

**Perpetually-Active, Self-Adaptive, Event-Driven Personal AI Backend**

---

## Overview

TILLU is a perpetually-active personal AI backend system designed to be:

- **Always Running**: Never sleeps, never stops
- **Always Learning**: Every interaction improves the system
- **Always Watching**: Continuously monitors world state
- **Always Ready**: Pre-computes context for instant responses
- **Zero Cost**: Engineered for free-tier permanence

## Architecture

### Three Concurrent Processes

```
┌─────────────────────────────────────────────────────────────────┐
│                     TILLU SYSTEM                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   GATEWAY    │  │    ENGINE    │  │    DAEMON    │           │
│  │  (FastAPI)   │  │    (n8n)     │  │  (Python)    │           │
│  │              │  │              │  │              │           │
│  │ • Public API │  │ • Scheduled  │  │ • 11 Loops   │           │
│  │ • Real-time  │  │   Workflows  │  │ • Always-on  │           │
│  │ • WebSocket  │  │ • LangChain  │  │ • Monitoring │           │
│  │              │  │   Chains     │  │              │           │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘           │
│         │                  │                  │                   │
│         └──────────────────┼──────────────────┘                   │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │  REDIS PUB/SUB │                            │
│                    │   (Upstash)   │                            │
│                    └───────┬───────┘                            │
│                            │                                     │
│              ┌─────────────┼─────────────┐                      │
│              ▼             ▼             ▼                      │
│      ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│      │ SUPABASE │  │  HF API  │  │  LLM API │                   │
│      │    +     │  │          │  │          │                   │
│      │ pgvector │  │          │  │          │                   │
│      └──────────┘  └──────────┘  └──────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

**📖 For complete setup instructions, see [SETUP_GUIDE.md](SETUP_GUIDE.md)**

### TL;DR — Get Running in 5 Minutes

```bash
# 1. Clone and install
git clone https://github.com/yourusername/tillu-backend.git
cd tillu-backend
./scripts/setup.sh  # or setup.ps1 on Windows

# 2. Configure (minimum required)
cp .env.example .env
# Edit .env and add:
#   SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
#   REDIS_URL, GROQ_API_KEY

# 3. Apply database schema
# Paste supabase/schema.sql into Supabase SQL Editor and run

# 4. Start services
# Terminal 1:
uvicorn app.main:app --reload

# Terminal 2:
python -m daemon.core

# 5. Test
open http://localhost:8000/docs
```

### Docker Quick Start

```bash
# 1. Configure .env (same as above)
cp .env.example .env
# Edit with your credentials

# 2. Start everything
docker compose up -d

# 3. View logs
docker compose logs -f

# 4. Test
open http://localhost:8000/docs
```

### What You Need

| Required | Get it from |
|----------|-------------|
| Supabase account | [supabase.com](https://supabase.com) (free) |
| Upstash Redis | [upstash.com](https://upstash.com) (free) |
| Groq API key | [console.groq.com](https://console.groq.com) (free) |

**Everything else is optional** — TILLU works with just these three.

## API Documentation

### Authentication

All API endpoints require Bearer token authentication:

```
Authorization: Bearer <supabase-jwt-token>
```

### Core Endpoints

#### Send a Message

```http
POST /api/v1/message
Content-Type: application/json
Authorization: Bearer <token>

{
  "type": "text",
  "text": "What's the weather like today?",
  "client_id": "optional-client-id"
}
```

#### Event Stream (SSE)

```http
GET /api/v1/stream
Authorization: Bearer <token>
```

#### Memory Search

```http
POST /api/v1/memory/search
Authorization: Bearer <token>

{
  "query": "my preferences about work schedule",
  "limit": 10
}
```

#### Health Check

```http
GET /api/v1/health
```

## Configuration

### Environment Variables

See `.env.example` for all required environment variables.

### Key Settings

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase service role key | Yes |
| `REDIS_URL` | Redis connection URL | Yes |
| `GROQ_API_KEY` | Groq API key | Yes |
| `HF_TOKEN` | Hugging Face token | Recommended |

## Cognitive Architecture

### Context Assembler (7 Tiers)

1. **Identity** (< 5ms): User profile, personality params
2. **Temporal** (< 2ms): Time of day, active hours
3. **Emotional State** (< 10ms): 7-day averages, stress level
4. **Immediate Memory** (< 20ms): Last 20 conversation turns
5. **Semantic Memory** (< 50ms): pgvector similarity search
6. **Situational** (< 15ms): Tasks, goals, pending events
7. **World State** (< 10ms): Breaking news, financial alerts

### Chain Registry

| Chain | Type | Trigger | Model |
|-------|------|---------|-------|
| Conversational | ConversationChain | small_talk, general_query | Groq 70B/8B |
| Research | LangGraph StateGraph | research_request | Cerebras/Groq |
| ReAct Agent | ReAct Agent | action_required | Gemini Pro |
| Analysis | LLMChain | pattern_query | Cerebras 70B |
| Empathy | ConversationChain | distress, sadness | Groq 70B |

## Daemon Loops

| Loop | Interval | Purpose |
|------|----------|---------|
| Heartbeat | 60s | System health ping |
| Financial Watcher | 15m | Asset price monitoring |
| Web Change Detector | 30m | URL change detection |
| News Urgency Scanner | 10m | News escalation |
| Pattern Recognition | 1h | Behavioral analysis |
| Context Pre-Computer | 1h | Context caching |
| Rate Limit Tracker | 5m | API quota management |
| Free Tier Governor | 1h | Resource governance |
| Goal Probability | 6h | Completion forecasting |
| Emotion Trend | 30m | Emotional state tracking |
| Relationship Monitor | 6h | Birthday/interaction check |

## Development

### Project Structure

```
tillu-backend/
├── app/                    # Main application
│   ├── api/               # FastAPI routes
│   ├── chains/            # LangChain chains
│   ├── memory/            # Memory components
│   ├── models/            # Pydantic models
│   ├── tools/             # LangChain tools
│   ├── transformers/      # HF transformers
│   ├── utils/             # Utilities
│   ├── config.py          # Configuration
│   └── main.py            # App entry point
├── daemon/                # Background daemon
│   └── core.py            # 11 async loops
├── n8n/                   # n8n workflows
│   └── workflows/         # Workflow definitions
├── supabase/              # Database
│   └── schema.sql         # Complete schema
├── deployments/           # Deployment configs
│   ├── render/           # Render.com
│   └── huggingface/      # HF Spaces
├── tests/                 # Test suite
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app tests/

# Linting
black app/
isort app/
flake8 app/
```

## Deployment

### Render (Primary)

See `deployments/render/` for configuration.

### Docker

```bash
# Build
docker build -t tillu-backend .

# Run
docker run -p 8000:8000 --env-file .env tillu-backend
```

## Cost Structure

All services used have free tiers:

| Service | Free Tier | TILLU Usage |
|---------|-----------|-------------|
| Supabase | 500MB + 500k requests | Primary storage |
| Upstash Redis | 10k ops/day | Caching + pub/sub |
| Groq | 14.4k tokens/min | Primary LLM |
| Cerebras | ~500 req/day | Deep reasoning |
| Hugging Face | Rate limited | Embeddings + NLP |
| NewsAPI | 100 req/day | News feed |
| CoinGecko | Unlimited | Crypto prices |

## Roadmap

### Phase 1: Foundation ✓
- [x] Supabase schema
- [x] FastAPI gateway
- [x] Basic conversational chain
- [x] Context assembler (Tiers 1-3)

### Phase 2: Memory
- [ ] pgvector setup
- [ ] Embedding pipeline
- [ ] Full context assembler
- [ ] CombinedMemory

### Phase 3: Intelligence
- [ ] Transformer pipeline
- [ ] All 10 chains
- [ ] LangGraph research agent
- [ ] Tool registry (32 tools)

### Phase 4: Autonomy
- [ ] n8n workflows
- [ ] Daemon all 11 loops
- [ ] Redis event system
- [ ] SSE/WebSocket delivery

### Phase 5: Real World
- [ ] SearXNG deployment
- [ ] News sources
- [ ] Financial monitoring
- [ ] Web change monitor

### Phase 6: Adaptation
- [ ] Personality evolution
- [ ] Self-critique
- [ ] Weekly analytics
- [ ] Routing optimization

### Phase 7: Production
- [ ] LangSmith tracing
- [ ] Error handling
- [ ] Keepalive ring
- [ ] Load testing

## License

MIT License - See LICENSE file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/tillu-backend/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/tillu-backend/discussions)

---

**TILLU runs. TILLU watches. TILLU learns. TILLU thinks. Whether you're there or not.**
