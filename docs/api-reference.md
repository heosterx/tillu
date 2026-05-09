# TILLU API Reference

## Base URL

```
Production: https://tillu-gateway.onrender.com
Development: http://localhost:8000
```

## Authentication

All API endpoints require Bearer token authentication:

```
Authorization: Bearer <supabase-jwt-token>
```

## Core Endpoints

### Send a Message

Process any input (text, audio, image, document, location).

```http
POST /api/v1/message
Content-Type: application/json
Authorization: Bearer <token>

{
  "type": "text",
  "text": "What's the weather like today?",
  "client_id": "optional-client-id",
  "metadata": {}
}
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | Yes | Message type: text, audio, image, document, location |
| text | string | Conditional | Text content (required for type=text) |
| media_url | string | Conditional | Media URL (for audio, image, document) |
| location | object | Conditional | {lat, lng} for location type |
| client_id | string | No | Client identifier |
| metadata | object | No | Additional metadata |

**Response:**

```json
{
  "response": {
    "type": "text",
    "content": "It's sunny and 72°F today...",
    "structured_data": {}
  },
  "personality_mode": "sharp",
  "queued_events": [],
  "intelligence_packet": null,
  "meta": {
    "chain": "conversational",
    "model": "groq-llama-3.1-8b",
    "latency_ms": 450,
    "tokens_used": 128,
    "intent_class": "general_query",
    "personality_mode": "sharp"
  },
  "sources": [],
  "session_id": "uuid"
}
```

### Event Stream (SSE)

Subscribe to real-time events via Server-Sent Events.

```http
GET /api/v1/stream
Authorization: Bearer <token>
Accept: text/event-stream
```

**Event Types:**

```
event: connected
data: {"message": "Connected to TILLU event stream"}

event: tillu_event
data: {
  "event_id": "uuid",
  "event_type": "breaking_news",
  "urgency": 9,
  "source_agent": "daemon",
  "content": {...},
  "personality_mode": "urgent"
}
```

### Memory Search

Search semantic memory using vector similarity.

```http
POST /api/v1/memory/search
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "my preferences about work schedule",
  "types": ["preference", "fact"],
  "date_range_start": "2024-01-01T00:00:00Z",
  "date_range_end": "2024-12-31T23:59:59Z",
  "limit": 10,
  "similarity_threshold": 0.75
}
```

**Response:**

```json
{
  "query": "my preferences about work schedule",
  "results": [
    {
      "id": "uuid",
      "content": "User prefers meetings before noon",
      "content_type": "preference",
      "category": "work",
      "confidence_score": 0.95,
      "similarity": 0.89,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total_found": 5,
  "search_time_ms": 45
}
```

### Store Memory

Explicitly store a knowledge item.

```http
POST /api/v1/memory/store
Authorization: Bearer <token>
Content-Type: application/json

{
  "content": "I prefer dark mode for all applications",
  "category": "preference",
  "confidence": 0.9
}
```

### Register Client

Register a new client with capabilities.

```http
POST /api/v1/register
Authorization: Bearer <token>
Content-Type: application/json

{
  "client_name": "My WhatsApp Bot",
  "client_type": "whatsapp",
  "capabilities": {
    "supports_text": true,
    "supports_audio": true,
    "supports_image": false,
    "supports_document": true,
    "supports_location": false,
    "supports_sse": false,
    "supports_websocket": false
  },
  "preferences": {
    "language": "en",
    "notification_style": "concise"
  }
}
```

**Response:**

```json
{
  "client_id": "uuid",
  "api_key": "tillu_xxx...",
  "registered_at": "2024-01-20T15:30:00Z",
  "message": "Client registered successfully"
}
```

### Get Intelligence

Pull compiled intelligence packets.

```http
GET /api/v1/intelligence?since=2024-01-20T00:00:00Z&types=news,financial&urgency_min=5
Authorization: Bearer <token>
```

### Health Check

Check system health status.

```http
GET /api/v1/health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": 1705762800,
  "services": [
    {
      "service": "supabase",
      "status": "healthy",
      "response_time_ms": 50,
      "last_check": 1705762800
    },
    {
      "service": "redis",
      "status": "healthy",
      "response_time_ms": 10,
      "last_check": 1705762800
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

### Get Analytics

Get usage metrics and quality scores.

```http
GET /api/v1/analytics?period=24h
Authorization: Bearer <token>
```

**Response:**

```json
{
  "period": "24h",
  "total_interactions": 150,
  "avg_response_time_ms": 850,
  "interactions_by_chain": {
    "conversational": 120,
    "research": 15,
    "analysis": 15
  },
  "avg_quality_scores": {
    "accuracy": 0.85,
    "helpfulness": 0.88,
    "personality_fit": 0.82
  },
  "api_usage": {
    "groq": {"requests": 150, "tokens": 45000},
    "hf_embedding": {"requests": 300}
  },
  "events_generated": 25,
  "events_by_type": {
    "news": 15,
    "financial": 5,
    "task_reminder": 5
  }
}
```

## Events API

### List Events

```http
GET /api/v1/events?status=pending&urgency_min=1&limit=50
Authorization: Bearer <token>
```

### Acknowledge Event

```http
POST /api/v1/events/{event_id}/acknowledge
Authorization: Bearer <token>
```

### Dismiss Event

```http
POST /api/v1/events/{event_id}/dismiss
Authorization: Bearer <token>
```

### Create Web Monitor

```http
POST /api/v1/events/monitor
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://example.com/news",
  "name": "News Page Monitor",
  "css_selector": ".headline",
  "check_interval": 30
}
```

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message",
  "status_code": 400,
  "error_code": "INVALID_REQUEST"
}
```

**Common Error Codes:**

| Status | Error Code | Description |
|--------|------------|-------------|
| 400 | INVALID_REQUEST | Malformed request |
| 401 | UNAUTHORIZED | Missing/invalid token |
| 403 | FORBIDDEN | Insufficient permissions |
| 404 | NOT_FOUND | Resource not found |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server error |
| 503 | SERVICE_UNAVAILABLE | Service temporarily unavailable |

## Rate Limiting

API endpoints are rate limited per user:

- **Per Minute**: 60 requests
- **Per Hour**: 1000 requests

Rate limit headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705762860
```

## WebSocket (Future)

Bidirectional WebSocket support coming in Phase 4:

```
WS /api/v1/ws
Authorization: Bearer <token>
```

## Client Responsibilities

1. **Register capabilities** → TILLU formats accordingly
2. **Subscribe to stream** → receive proactive intelligence
3. **Acknowledge urgent events** → TILLU knows you received them
4. **Nothing else** → TILLU handles all intelligence production

## Response Contract

All successful responses include:

```json
{
  "response": {
    "type": "text|json|structured",
    "content": "...",
    "structured_data": {}
  },
  "personality_mode": "sharp|warm|empathic|urgent",
  "queued_events": [],
  "meta": {
    "chain": "...",
    "model": "...",
    "latency_ms": 0,
    "tokens": 0,
    "sources": []
  }
}
```
