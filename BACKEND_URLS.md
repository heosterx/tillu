# TILLU Backend - Complete URL Reference

## Base URL
```
http://localhost:8000  (development)
https://tillu-gateway.onrender.com  (production)
```

---

## Core Gateway API (`/api/v1`)

### Message Processing
- **POST** `/api/v1/message` - Process inbound message (text, audio, image, document, location)
  - Auth: Bearer token required
  - Response: MessageResponse with chain metadata, sources, and intelligence packet

### Event Streaming
- **GET** `/api/v1/stream` - SSE long-lived connection for real-time events
  - Auth: Bearer token required
  - Returns: Server-Sent Events stream

### Client Management
- **POST** `/api/v1/register` - Register client + capabilities + preferences
  - Auth: Bearer token required
  - Request: ClientRegistrationRequest
  - Response: ClientRegistrationResponse with API key

### Intelligence Retrieval
- **GET** `/api/v1/intelligence` - Pull compiled intelligence packets
  - Auth: Bearer token required
  - Query params: `since`, `types`, `urgency_min`
  - Returns: Pending events/intelligence packets

### System Status
- **GET** `/api/v1/health` - System health check (all services, API limits, queue depths)
  - No auth required
  - Returns: HealthResponse with service statuses

### Analytics
- **GET** `/api/v1/analytics` - Usage metrics, quality scores, system performance
  - Auth: Bearer token required
  - Query params: `period` (default: "24h")
  - Returns: Analytics data with interaction breakdown

---

## Memory API (`/api/v1/memory`)

### Search
- **POST** `/api/v1/memory/search` - Semantic memory query across all stores
  - Auth: Bearer token required
  - Request: MemorySearchRequest (query, limit)
  - Response: MemorySearchResponse with ranked results from knowledge base, news, research

### Store
- **POST** `/api/v1/memory/store` - Explicitly store a knowledge item with embedding
  - Auth: Bearer token required
  - Query params: `content`, `content_type`, `category`
  - Returns: Success with memory_id

### Delete
- **DELETE** `/api/v1/memory/{memory_id}` - Delete a memory item
  - Auth: Bearer token required
  - Returns: Success confirmation

---

## Events API (`/api/v1/events`)

### List Events
- **GET** `/api/v1/events/` - List events for authenticated user
  - Auth: Bearer token required
  - Query params: `status` (default: "pending"), `urgency_min`, `limit` (default: 50)
  - Returns: List of events with count

### Acknowledge Event
- **POST** `/api/v1/events/{event_id}/acknowledge` - Mark event as acknowledged
  - Auth: Bearer token required
  - Returns: Success confirmation

### Dismiss Event
- **POST** `/api/v1/events/{event_id}/dismiss` - Dismiss an event
  - Auth: Bearer token required
  - Returns: Success confirmation

### Web Monitoring
- **POST** `/api/v1/events/monitor` - Register URL for web change monitoring
  - Auth: Bearer token required
  - Query params: `url`, `name`, `css_selector`, `check_interval`
  - Returns: Monitor creation confirmation with monitor_id

---

## Health Check Endpoints

### Basic Health
- **GET** `/health` - Basic health check
  - No auth required
  - Returns: `{"status": "healthy", "timestamp": ...}`

### Readiness Check
- **GET** `/ready` - Readiness check for Kubernetes/container orchestration
  - No auth required
  - Returns: Status with database and cache checks

### Liveness Check
- **GET** `/live` - Liveness check for Kubernetes/container orchestration
  - No auth required
  - Returns: `{"status": "alive", "timestamp": ...}`

---

## Metrics
- **GET** `/metrics` - Prometheus metrics endpoint
  - No auth required
  - Returns: Prometheus-formatted metrics

---

## Root Endpoints

### Root
- **GET** `/` - Root endpoint
  - No auth required
  - Returns: API info with name, version, status, docs link

### Version
- **GET** `/version` - Get API version
  - No auth required
  - Returns: Version and build info

---

## Internal Trigger API (`/internal/trigger`)
*Protected by `X-Cron-Secret` header*

### Morning Brief
- **POST** `/internal/trigger/morning-brief` - WF-02: Morning Intelligence Brief (7:00 AM IST)
  - Sends weather + calendar + tasks + news brief

### News Scan
- **POST** `/internal/trigger/news-scan` - News scan (every 30 min during active hours)

### Task Reminder
- **POST** `/internal/trigger/task-reminder` - Task reminder (9 AM and 9 PM IST)

### Evening Summary
- **POST** `/internal/trigger/evening-summary` - Evening summary (8:00 PM IST)

### Financial Watch
- **POST** `/internal/trigger/financial-watch` - Financial monitoring (every 15 min on market days)

### Memory Consolidation
- **POST** `/internal/trigger/memory-consolidation` - Memory consolidation (midnight IST)

### Weekly Analytics
- **POST** `/internal/trigger/weekly-analytics` - Weekly analytics (Sunday 8 PM IST)

### Personality Evolution
- **POST** `/internal/trigger/personality-evolution` - Personality evolution (Sunday 10 PM IST)

### Timetable Info
- **GET** `/internal/trigger/timetable` - Get full timetable for cron-job.org setup
  - Returns: All scheduled jobs with cron expressions and setup instructions

---

## Workflow Management API (`/internal/workflow`)
*Protected by `X-Cron-Secret` header*

### List Workflows
- **GET** `/internal/workflow/list` - List all workflows in n8n
  - Returns: Total count and workflow details (id, name, active status, updatedAt)

### Sync Workflows
- **POST** `/internal/workflow/sync` - Sync all workflow JSON files from repo to n8n
  - Creates new workflows and updates existing ones by name
  - Returns: SyncResponse with synced count and results

### Generate Workflow
- **POST** `/internal/workflow/generate` - LLM generates + deploys new workflow
  - Request: GenerateRequest (instruction, base_workflow_name)
  - Example: "Create a workflow that checks INR/USD rate every hour and alerts if it moves more than 1%"
  - Returns: Generated workflow details

### Activate Workflow
- **POST** `/internal/workflow/activate/{workflow_id}` - Activate a workflow by ID

### Deactivate Workflow
- **POST** `/internal/workflow/deactivate/{workflow_id}` - Deactivate a workflow by ID

### Self-Upgrade
- **POST** `/internal/workflow/self-upgrade` - TILLU's self-upgrade endpoint
  - Called by n8n WF-17 (weekly self-audit) to sync latest workflows from repo
  - Returns: Upgrade status with synced/failed counts

---

## Documentation

### Swagger UI
- **GET** `/docs` - Interactive API documentation (development only)

### ReDoc
- **GET** `/redoc` - Alternative API documentation (development only)

---

## Authentication

All endpoints marked with "Auth: Bearer token required" expect:
```
Authorization: Bearer <token>
```

Internal endpoints (triggers, workflows) use:
```
X-Cron-Secret: <TILLU_CRON_SECRET>
```

---

## Response Models

### MessageResponse
```json
{
  "response": {"type": "text", "content": "..."},
  "personality_mode": "sharp|warm|analytical",
  "queued_events": [],
  "intelligence_packet": null,
  "meta": {
    "chain": "conversational|research|analysis",
    "model": "groq-llama-3.1-8b",
    "latency_ms": 850,
    "tokens_used": 150,
    "intent_class": "general_query",
    "personality_mode": "sharp"
  },
  "sources": [],
  "session_id": "uuid"
}
```

### MemorySearchResponse
```json
{
  "query": "search query",
  "results": [
    {
      "id": "uuid",
      "content": "...",
      "content_type": "fact|news|research",
      "category": "...",
      "source_type": "knowledge_base|news_article|research",
      "confidence_score": 0.85,
      "similarity": 0.75,
      "created_at": "2026-05-10T..."
    }
  ],
  "total_found": 5,
  "search_time_ms": 250
}
```

### HealthResponse
```json
{
  "status": "healthy|degraded",
  "version": "0.1.0",
  "timestamp": 1715000000,
  "services": [
    {
      "service": "supabase|redis",
      "status": "healthy|degraded|down",
      "response_time_ms": 50,
      "last_check": 1715000000
    }
  ],
  "api_limits": {
    "groq": {"remaining": 14400, "reset_time": "1h"},
    "cerebras": {"remaining": 500, "reset_time": "24h"}
  },
  "queue_depths": {
    "tillu:events:urgent": 0,
    "tillu:events:normal": 5,
    "tillu:events:low": 23
  }
}
```

---

## Environment Configuration

Key environment variables for URL configuration:
- `SUPABASE_URL` - Supabase API URL
- `SUPABASE_KEY` - Supabase public key
- `REDIS_URL` - Redis connection URL
- `SEARXNG_URL` - SearXNG service URL (default: https://tillu-ai-tillu-searxng.hf.space)
- `WEBSEARCH_URL` - WebSearch service URL (default: https://tillu-ai-tillu-websearch.hf.space)
- `PLAYWRIGHT_SERVICE_URL` - Playwright service URL (default: http://localhost:3001)
- `N8N_URL` - n8n instance URL
- `N8N_WEBHOOK_URL` - n8n webhook URL
- `TILLU_CRON_SECRET` - Secret for cron job authentication
- `CORS_ORIGINS` - Allowed CORS origins (default: http://localhost:3000)

---

## Summary

**Total Endpoints: 30+**

- **Public API**: 11 endpoints (message, stream, register, intelligence, health, analytics, memory search/store/delete, events)
- **Health Checks**: 3 endpoints (health, ready, live)
- **Internal Triggers**: 8 endpoints (morning-brief, news-scan, task-reminder, evening-summary, financial-watch, memory-consolidation, weekly-analytics, personality-evolution)
- **Workflow Management**: 6 endpoints (list, sync, generate, activate, deactivate, self-upgrade)
- **Utilities**: 3 endpoints (root, version, metrics)

All endpoints follow RESTful conventions and return JSON responses.
