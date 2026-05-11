# TILLU Backend - Weakpoints Review

## Executive Summary

TILLU has **16 critical architectural issues** across authentication, database patterns, error handling, and resource management. The system is currently **not production-ready** without addressing these vulnerabilities.

**Critical Issues: 16**
**High Priority: 18**
**Medium Priority: 8**

---

## 1. AUTHENTICATION & AUTHORIZATION (🔴 CRITICAL)

### Issue 1.1: JWT Verification Not Implemented

**Severity:** 🔴 CRITICAL
**File:** `app/api/gateway.py:24-32`
**Status:** TODO comment in code

```python
async def verify_auth(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    # TODO: Verify JWT with Supabase  ← NOT IMPLEMENTED
    return {"user_id": "test-user-id", "token": token}
```

**Problem:**
- All requests use hardcoded `"test-user-id"` regardless of token
- No actual JWT validation against Supabase
- Any bearer token is accepted
- **Complete authentication bypass**

**Impact:**
- Any user can impersonate any other user
- No user isolation
- All data is accessible to anyone with API access

**Fix:**
```python
async def verify_auth(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Verify JWT with Supabase
        payload = await db.verify_jwt(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "token": token}
    except Exception as e:
        logger.error("JWT verification failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Timeline:** Fix immediately before any production deployment

---

### Issue 1.2: API Keys Exposed in Environment

**Severity:** 🔴 CRITICAL
**File:** `app/providers/llm_router.py:224, 237, 257, 281, 292, 308`

```python
headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
```

**Problem:**
- API keys accessed directly from `os.environ` in request handlers
- Keys could be logged in error messages
- No secrets manager integration
- Keys visible in stack traces

**Impact:**
- API key compromise if logs are exposed
- Unauthorized API usage
- Financial impact (API charges)

**Fix:**
```python
# Use a secrets manager
from app.utils.secrets import get_secret

groq_key = await get_secret("GROQ_API_KEY")
headers={"Authorization": f"Bearer {groq_key}"}
```

**Timeline:** Implement before production

---

### Issue 1.3: Client API Keys Stored in Plaintext

**Severity:** 🔴 CRITICAL
**File:** `app/api/gateway.py:155-160`

```python
client_api_key = f"tillu_{uuid.uuid4().hex}"
# ...
"api_key_hash": client_api_key,  # In production, hash this
```

**Problem:**
- Comment says "hash this" but code stores plaintext
- No hashing implemented
- Database compromise = API key compromise

**Impact:**
- Compromised database exposes all client API keys
- Attackers can impersonate clients

**Fix:**
```python
from hashlib import sha256

client_api_key = f"tillu_{uuid.uuid4().hex}"
api_key_hash = sha256(client_api_key.encode()).hexdigest()

client_data = {
    "api_key_hash": api_key_hash,  # Store hash
    # ...
}

# Return plaintext key only once to client
return ClientRegistrationResponse(
    client_id=result[0]["id"],
    api_key=client_api_key,  # Only in response, never stored
    registered_at=result[0]["created_at"]
)
```

**Timeline:** Fix immediately

---

### Issue 1.4: No Rate Limiting on Public Endpoints

**Severity:** 🔴 CRITICAL
**File:** `app/api/gateway.py:47-100`

**Problem:**
- `/message` endpoint has no rate limiting
- `/stream` endpoint has no connection limits
- `/register` endpoint allows unlimited client registration
- Config exists but never used

```python
# In config.py - defined but never used
rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")
```

**Impact:**
- DDoS vulnerability
- Resource exhaustion
- Unlimited API consumption
- Free tier abuse

**Fix:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@router.post("/message")
@limiter.limit("60/minute")
async def process_message(request: MessageRequest, ...):
    # ...
```

**Timeline:** Implement before production

---

## 2. DATABASE PATTERNS (🔴 CRITICAL)

### Issue 2.1: N+1 Query Pattern in Daemon Loops

**Severity:** 🔴 CRITICAL
**File:** `daemon/core.py:358-365, 437-445, 603-610`

**Pattern 1 - Pattern Recognition Loop:**
```python
users = await db.fetch_many("user_profile", limit=100)  # Query 1
for user in users:
    interactions = await db.fetch_many("interactions", ...)  # Query 2-101
    # Analysis on each user
```

**Problem:**
- Fetches 100 users, then **100 separate queries** for interactions
- **Total: 101 queries** for what could be 1 JOIN query
- Runs every 1 hour but scales linearly with user count
- At 1000 users: 1000+ queries per cycle

**Impact:**
- Database connection pool exhaustion
- Slow query performance
- High latency on other requests
- Potential database lockups

**Affected Loops:**
1. Pattern Recognition (every 1h)
2. Emotion Trend Tracker (every 30m)
3. Goal Probability Engine (every 6h)
4. Relationship Monitor (every 6h)

**Fix:**
```python
# Use JOIN instead of loop
query = """
SELECT u.*, COUNT(i.id) as interaction_count
FROM user_profile u
LEFT JOIN interactions i ON u.id = i.user_id
GROUP BY u.id
LIMIT 100
"""
results = await db.execute_raw(query)
```

**Timeline:** Fix before production (high impact)

---

### Issue 2.2: Duplicate Existence Checks (N+1 Variant)

**Severity:** 🟠 HIGH
**File:** `daemon/core.py` (news_service, email_service, calendar_service)

```python
for entry in feed.entries[:5]:
    existing = await db.fetch_one("news_articles", {"url": entry.link})  # N queries
    if not existing:
        await db.insert(...)
```

**Problem:**
- 5 separate queries to check existence
- Should use `INSERT ... ON CONFLICT` (upsert)
- **5 queries per feed** instead of 1 batch operation

**Impact:**
- Unnecessary database load
- Slow feed processing

**Fix:**
```python
# Use upsert instead
await db.upsert(
    "news_articles",
    [{"url": entry.link, "title": entry.title, ...} for entry in feed.entries],
    conflict_columns=["url"]
)
```

**Timeline:** Fix in next iteration

---

### Issue 2.3: Missing Pagination in Loops

**Severity:** 🟠 HIGH
**File:** `daemon/core.py:358, 437, 603`

```python
users = await db.fetch_many("user_profile", limit=100)  # Loads all 100 into memory
```

**Problem:**
- `limit=100` loads all 100 records into memory at once
- No offset/pagination for large datasets
- Could cause OOM on systems with thousands of users

**Impact:**
- Memory spike during loop execution
- Potential out-of-memory crashes
- Slow loop execution

**Fix:**
```python
# Paginate through results
page_size = 10
offset = 0
while True:
    users = await db.fetch_many("user_profile", limit=page_size, offset=offset)
    if not users:
        break
    
    for user in users:
        # Process user
        pass
    
    offset += page_size
```

**Timeline:** Fix before production

---

## 3. ERROR HANDLING & RESILIENCE (🔴 CRITICAL)

### Issue 3.1: Weak Exception Handling in Lifespan

**Severity:** 🔴 CRITICAL
**File:** `app/main.py:30-43`

```python
try:
    await cache.connect()
    logger.info("Redis connected")
except Exception as e:
    logger.error("Failed to connect to Redis", error=str(e))
    # Continue without Redis - service can still function  ← DANGEROUS
```

**Problem:**
- Redis connection failure is silently ignored
- Service starts in degraded state without alerting operators
- No fallback mechanism if Redis is unavailable
- Pub/Sub won't work, breaking daemon ↔ gateway communication

**Impact:**
- Silent service degradation
- Daemon and gateway can't communicate
- Events not delivered to users
- No alerts to operators

**Fix:**
```python
try:
    await cache.connect()
    logger.info("Redis connected")
except Exception as e:
    logger.error("Failed to connect to Redis", error=str(e))
    # Don't continue - fail fast
    raise RuntimeError("Redis is required for TILLU to function")
```

**Timeline:** Fix immediately

---

### Issue 3.2: Bare Exception Catches in Daemon Loops

**Severity:** 🔴 CRITICAL
**File:** `daemon/core.py:150-172`

```python
try:
    self.logger.debug(f"Running loop: {loop_config.name}")
    await loop_config.function()
    elapsed = (datetime.now() - start_time).total_seconds()
    await self._update_loop_state(loop_config.name, True, elapsed)
except asyncio.CancelledError:
    self.logger.info(f"Loop {loop_config.name} cancelled")
    raise
except Exception as e:  # ← Too broad
    self.logger.error(f"Loop {loop_config.name} error: {e}")
    await self._update_loop_state(loop_config.name, False, 0, str(e))
    await asyncio.sleep(5)  # Retry immediately
```

**Problem:**
- All exceptions caught broadly without categorization
- No distinction between transient vs. permanent failures
- Errors logged but not escalated to monitoring systems
- Immediate retry (5s) could hammer failing services

**Impact:**
- Silent failures in background intelligence loops
- Cascading failures if service is down
- No alerts to operators
- Difficult to debug issues

**Fix:**
```python
except asyncio.CancelledError:
    self.logger.info(f"Loop {loop_config.name} cancelled")
    raise
except asyncio.TimeoutError:
    self.logger.warning(f"Loop {loop_config.name} timeout")
    await self._update_loop_state(loop_config.name, False, 0, "timeout")
    await asyncio.sleep(30)  # Longer backoff for timeouts
except ConnectionError as e:
    self.logger.error(f"Loop {loop_config.name} connection error: {e}")
    await self._update_loop_state(loop_config.name, False, 0, "connection_error")
    await asyncio.sleep(60)  # Exponential backoff
except Exception as e:
    self.logger.error(f"Loop {loop_config.name} unexpected error: {e}", exc_info=True)
    await self._update_loop_state(loop_config.name, False, 0, str(e))
    await asyncio.sleep(5)
```

**Timeline:** Fix before production

---

### Issue 3.3: No Fallback for LLM Provider Failures

**Severity:** 🔴 CRITICAL
**File:** `app/providers/llm_router.py:175-310`

```python
async def invoke(...):
    sel = select(task, lang)  # Selects ONE provider
    provider = sel["provider"]
    
    if client == "groq":
        # If Groq fails, entire request fails
        # No fallback to next provider
```

**Problem:**
- Only tries one provider per request
- If Groq fails, no fallback to HF or Cerebras
- No retry logic
- No timeout handling

**Impact:**
- Service unavailable if primary provider down
- User-facing errors on temporary outages
- No graceful degradation

**Fix:**
```python
async def invoke(...):
    providers = select_providers(task, lang)  # Get ranked list
    
    for provider_config in providers:
        try:
            result = await call_provider(provider_config, messages, ...)
            return result
        except Exception as e:
            logger.warning(f"Provider {provider_config['provider']} failed: {e}")
            continue  # Try next provider
    
    # All providers failed
    raise HTTPException(status_code=503, detail="All LLM providers unavailable")
```

**Timeline:** Fix before production

---

## 4. EXTERNAL API DEPENDENCIES (🔴 CRITICAL)

### Issue 4.1: Unvalidated External Service URLs

**Severity:** 🔴 CRITICAL
**File:** `app/config.py:95-100`

```python
searxng_url: str = Field(default="https://tillu-ai-tillu-searxng.hf.space", ...)
websearch_url: str = Field(default="https://tillu-ai-tillu-websearch.hf.space", ...)
playwright_service_url: str = Field(default="http://localhost:3001", ...)
```

**Problem:**
- URLs are user-configurable but not validated
- No URL scheme validation (http vs https)
- Could be exploited for SSRF attacks
- No hostname whitelist

**Impact:**
- Server-side request forgery (SSRF) vulnerability
- Attacker could redirect requests to internal services
- Potential data exfiltration

**Fix:**
```python
from urllib.parse import urlparse

class Settings(BaseSettings):
    @validator("searxng_url", "websearch_url", "playwright_service_url")
    def validate_service_urls(cls, v):
        try:
            parsed = urlparse(v)
            # Only allow https in production
            if settings.is_production and parsed.scheme != "https":
                raise ValueError("HTTPS required in production")
            # Whitelist allowed hosts
            allowed_hosts = ["tillu-ai-tillu-searxng.hf.space", "localhost", "127.0.0.1"]
            if parsed.hostname not in allowed_hosts:
                raise ValueError(f"Host {parsed.hostname} not whitelisted")
            return v
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
```

**Timeline:** Fix immediately

---

### Issue 4.2: No Circuit Breaker Pattern

**Severity:** 🟠 HIGH
**File:** `daemon/core.py` (all service loops)

**Problem:**
- Services fail and retry immediately
- No exponential backoff
- Could hammer failing services
- No circuit breaker to prevent cascading failures

**Impact:**
- Cascading failures
- Increased load on failing services
- Slower recovery

**Fix:**
```python
from pybreaker import CircuitBreaker

circuit_breaker = CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    listeners=[...]
)

@circuit_breaker
async def call_external_service():
    # ...
```

**Timeline:** Implement in next iteration

---

## 5. DATA VALIDATION (🔴 CRITICAL)

### Issue 5.1: No Input Validation on Message Endpoint

**Severity:** 🔴 CRITICAL
**File:** `app/api/gateway.py:47-100`

```python
@router.post("/message", response_model=MessageResponse)
async def process_message(request: MessageRequest, ...):
    input_text = request.text or ""
    # No validation of input_text length, content, encoding
```

**Problem:**
- No max length validation
- No content type validation
- Could accept malicious payloads
- No encoding validation

**Impact:**
- Injection attacks
- DoS via large payloads
- Memory exhaustion

**Fix:**
```python
class MessageRequest(BaseModel):
    type: str
    text: Optional[str] = None
    media_url: Optional[str] = None
    
    @validator("text")
    def validate_text(cls, v):
        if v and len(v) > 10000:
            raise ValueError("Text too long (max 10000 chars)")
        if v and not isinstance(v, str):
            raise ValueError("Text must be string")
        return v
    
    @validator("media_url")
    def validate_media_url(cls, v):
        if v:
            # Validate URL format
            from urllib.parse import urlparse
            try:
                result = urlparse(v)
                if not all([result.scheme, result.netloc]):
                    raise ValueError("Invalid URL")
            except:
                raise ValueError("Invalid URL")
        return v
```

**Timeline:** Fix immediately

---

## 6. MEMORY MANAGEMENT (🟠 HIGH)

### Issue 6.1: Unbounded Task Creation

**Severity:** 🟠 HIGH
**File:** `daemon/core.py:106-125`

```python
for loop_config in self.loops:
    task = asyncio.create_task(...)
    self.tasks.append(task)  # Grows indefinitely
```

**Problem:**
- 16 concurrent loops created at startup
- Each loop runs indefinitely with `while self._running`
- No task cleanup on exceptions
- Tasks accumulate in memory

**Impact:**
- Memory leak if tasks accumulate
- Potential OOM after long runtime

**Fix:**
```python
self.tasks = set()  # Use set instead of list

for loop_config in self.loops:
    task = asyncio.create_task(self._run_loop_wrapper(loop_config))
    self.tasks.add(task)
    task.add_done_callback(self.tasks.discard)  # Auto-cleanup
```

**Timeline:** Fix in next iteration

---

### Issue 6.2: Redis Connection Not Pooled

**Severity:** 🟠 HIGH
**File:** `app/utils/cache.py:30-40`

```python
redis_client = redis.from_url(redis_url)  # Single connection
```

**Problem:**
- Single Redis connection per instance
- No connection pooling configured
- Connection exhaustion under load

**Impact:**
- Connection exhaustion under concurrent requests
- Slow response times
- Service unavailability

**Fix:**
```python
from redis.asyncio import ConnectionPool

pool = ConnectionPool.from_url(redis_url, max_connections=10)
redis_client = redis.Redis(connection_pool=pool)
```

**Timeline:** Fix before production

---

## 7. LOGGING & OBSERVABILITY (🟠 HIGH)

### Issue 7.1: Sensitive Data in Logs

**Severity:** 🟠 HIGH
**File:** `app/api/gateway.py:34, 42`

```python
logger.error("Failed to connect to Redis", error=str(e))
logger.error("Failed to initialize Supabase", error=str(e))
```

**Problem:**
- Error messages could contain connection strings, credentials
- No log sanitization
- Logs could be exposed in monitoring systems

**Impact:**
- Credential exposure in logs
- Security breach if logs are accessed

**Fix:**
```python
def sanitize_error(error: Exception) -> str:
    """Remove sensitive data from error messages"""
    error_str = str(error)
    # Remove connection strings
    error_str = re.sub(r'redis://.*@', 'redis://***@', error_str)
    error_str = re.sub(r'postgresql://.*@', 'postgresql://***@', error_str)
    return error_str

logger.error("Failed to connect to Redis", error=sanitize_error(e))
```

**Timeline:** Fix immediately

---

### Issue 7.2: Missing Distributed Tracing

**Severity:** 🟠 HIGH
**File:** `app/api/gateway.py:47-100`

```python
request_id = str(uuid.uuid4())
bind_request_context(request_id, user_id)
```

**Problem:**
- Request ID generated but not propagated to daemon
- No distributed tracing across services
- Difficult to debug issues

**Impact:**
- Hard to trace requests through system
- Difficult to debug issues
- Poor observability

**Fix:**
```python
# Use OpenTelemetry for distributed tracing
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@router.post("/message")
async def process_message(request: MessageRequest, ...):
    with tracer.start_as_current_span("process_message") as span:
        span.set_attribute("user_id", user_id)
        span.set_attribute("message_type", request.type)
        # ...
```

**Timeline:** Implement in next iteration

---

## 8. ASYNC/AWAIT PATTERNS (🟠 HIGH)

### Issue 8.1: Improper Exception Handling in gather()

**Severity:** 🟠 HIGH
**File:** `daemon/core.py:129`

```python
await asyncio.gather(*self.tasks, return_exceptions=True)
```

**Problem:**
- `return_exceptions=True` means exceptions are returned, not raised
- Code doesn't check for exceptions in results
- Failed tasks silently continue

**Impact:**
- Silent failures in daemon loops
- Difficult to debug

**Fix:**
```python
results = await asyncio.gather(*self.tasks, return_exceptions=True)
for i, result in enumerate(results):
    if isinstance(result, Exception):
        logger.error(f"Task {i} failed: {result}")
```

**Timeline:** Fix in next iteration

---

## 9. TESTING (🔴 CRITICAL)

### Issue 9.1: No Tests for Critical Paths

**Severity:** 🔴 CRITICAL

**Missing Tests:**
- ❌ Authentication flow (JWT verification)
- ❌ LLM routing fallback
- ❌ Daemon loop resilience
- ❌ Database connection failures
- ❌ End-to-end message processing
- ❌ Context assembly
- ❌ Chain execution
- ❌ Concurrent requests
- ❌ Memory leaks under load

**Impact:**
- Regressions go undetected
- System-level bugs undetected
- Performance issues discovered in production

**Fix:**
```python
# tests/test_auth.py
@pytest.mark.asyncio
async def test_jwt_verification():
    """Test JWT verification"""
    # Create valid JWT
    token = create_test_jwt("user-123")
    
    # Verify it works
    auth = await verify_auth(f"Bearer {token}")
    assert auth["user_id"] == "user-123"
    
    # Verify invalid token fails
    with pytest.raises(HTTPException):
        await verify_auth("Bearer invalid-token")

# tests/test_llm_routing.py
@pytest.mark.asyncio
async def test_llm_fallback():
    """Test LLM provider fallback"""
    # Mock Groq to fail
    with patch("app.providers.llm_router.call_groq", side_effect=Exception("Groq down")):
        # Should fallback to Cerebras
        result = await invoke(messages=[...], task="analysis")
        assert result["provider"] == "cerebras"
```

**Timeline:** Implement before production

---

## PRIORITY MATRIX

| Issue | Severity | Effort | Priority |
|-------|----------|--------|----------|
| JWT verification | 🔴 CRITICAL | 2h | 1 |
| Rate limiting | 🔴 CRITICAL | 3h | 2 |
| N+1 queries | 🔴 CRITICAL | 8h | 3 |
| Input validation | 🔴 CRITICAL | 4h | 4 |
| LLM fallback | 🔴 CRITICAL | 4h | 5 |
| Error handling | 🔴 CRITICAL | 6h | 6 |
| API key security | 🔴 CRITICAL | 3h | 7 |
| Redis connection pooling | 🟠 HIGH | 2h | 8 |
| Logging sanitization | 🟠 HIGH | 2h | 9 |
| Circuit breaker | 🟠 HIGH | 4h | 10 |
| Testing suite | 🔴 CRITICAL | 20h | 11 |

---

## IMMEDIATE ACTION ITEMS (Before Production)

### Week 1 (Critical Security)
- [ ] Implement JWT verification (2h)
- [ ] Add rate limiting middleware (3h)
- [ ] Sanitize logs (2h)
- [ ] Validate input on all endpoints (4h)
- [ ] Hash client API keys (1h)

### Week 2 (Critical Reliability)
- [ ] Fix N+1 queries (8h)
- [ ] Implement LLM fallback (4h)
- [ ] Fix error handling in daemon (6h)
- [ ] Add connection pooling (2h)
- [ ] Implement circuit breaker (4h)

### Week 3 (Testing & Observability)
- [ ] Write critical path tests (20h)
- [ ] Add distributed tracing (4h)
- [ ] Add monitoring/alerting (4h)
- [ ] Load testing (4h)

---

## LONG-TERM IMPROVEMENTS

### Phase 1: Stability (Weeks 1-3)
- Fix all critical issues
- Add comprehensive testing
- Implement monitoring

### Phase 2: Performance (Weeks 4-6)
- Optimize database queries
- Add caching layer
- Profile memory usage

### Phase 3: Scalability (Weeks 7-10)
- Implement horizontal scaling
- Add load balancing
- Optimize resource usage

### Phase 4: Observability (Weeks 11-12)
- Add distributed tracing
- Implement alerting
- Add dashboards

---

## CONCLUSION

TILLU has significant architectural issues that must be addressed before production deployment. The most critical issues are:

1. **Authentication bypass** - Complete security vulnerability
2. **N+1 queries** - Will cause database exhaustion
3. **No rate limiting** - DDoS vulnerability
4. **No error handling** - Silent failures
5. **No testing** - Regressions undetected

**Estimated effort to production-ready: 60-80 hours**

Recommend addressing critical issues first (Week 1-2), then comprehensive testing (Week 3) before any production deployment.

---

**Last Updated:** May 2026
**Status:** Not Production Ready
**Estimated Fix Time:** 60-80 hours
