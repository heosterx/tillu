# TILLU Scraper v2 - Testing & Deployment Guide

## Quick Start

### Local Testing

```bash
# 1. Install dependencies
pip install -r deployments/huggingface/scraper-space/requirements.txt

# 2. Set environment variables (optional)
$env:LOG_LEVEL = "DEBUG"
$env:SEARXNG_URL = "http://localhost:8888"  # if running locally
$env:GROQ_API_KEY = "your-key-here"

# 3. Run the service
uvicorn deployments.huggingface.scraper-space.main:app --host 0.0.0.0 --port 7860 --reload

# 4. Test endpoints
curl http://localhost:7860/health
curl http://localhost:7860/status
```

---

## API Testing Examples

### 1. Health Check
```bash
curl -X GET http://localhost:7860/health
```

**Response**:
```json
{
  "status": "ok",
  "service": "tillu-scraper",
  "version": "2.0.0"
}
```

### 2. Service Status
```bash
curl -X GET http://localhost:7860/status
```

**Response**:
```json
{
  "service": "tillu-scraper",
  "version": "2.0.0",
  "engines": {
    "searxng": {
      "url": "https://tillu-ai-tillu-searxng.hf.space",
      "healthy": true
    },
    "duckduckgo": {"status": "fallback"},
    "google_lite": {"status": "last_resort"}
  },
  "scrapers": {
    "crawl4ai": {"available": true, "type": "primary"},
    "playwright": {"available": true, "type": "fallback"}
  },
  "groq_configured": true,
  "cache_size": 0,
  "uptime_seconds": 12.5,
  "requests_total": 0,
  "searches_total": 0,
  "scrapes_total": 0,
  "intelligence_total": 0,
  "errors_total": 0,
  "engine_hits": {
    "searxng": 0,
    "duckduckgo": 0,
    "google": 0
  },
  "cache_hits": 0,
  "rate_limit_window_count": 0
}
```

### 3. Web Search
```bash
curl -X POST http://localhost:7860/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "lang": "en",
    "max_results": 5,
    "scrape_content": false,
    "categories": "general"
  }'
```

**Response**:
```json
{
  "results": [
    {
      "title": "Artificial Intelligence - Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
      "snippet": "Artificial intelligence (AI) is the intelligence of machines...",
      "engine": "searxng",
      "score": 1.0,
      "content": null
    }
  ],
  "query": "artificial intelligence",
  "lang": "en",
  "total": 5,
  "source": "searxng",
  "cached": false
}
```

### 4. Web Scraping
```bash
curl -X POST http://localhost:7860/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
    "extract_text": true
  }'
```

**Response**:
```json
{
  "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
  "title": "Artificial Intelligence - Wikipedia",
  "text": "Artificial intelligence (AI) is the intelligence of machines...",
  "links": [
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://en.wikipedia.org/wiki/Deep_learning"
  ],
  "success": true,
  "error": null,
  "scrape_method": "crawl4ai",
  "metadata": {
    "crawl4ai_success": true,
    "links_found": 42,
    "content_length": 8234
  }
}
```

### 5. Search + Scrape
```bash
curl -X POST http://localhost:7860/search-and-scrape \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "lang": "en",
    "max_results": 5,
    "scrape_top": 2,
    "categories": "general"
  }'
```

**Response**:
```json
{
  "query": "machine learning",
  "lang": "en",
  "results": [
    {
      "title": "Machine Learning - Wikipedia",
      "url": "https://en.wikipedia.org/wiki/Machine_learning",
      "snippet": "Machine learning is a subset of artificial intelligence...",
      "engine": "searxng",
      "content": "Machine learning is a subset of artificial intelligence...",
      "scraped": true
    },
    {
      "title": "Machine Learning - Google Cloud",
      "url": "https://cloud.google.com/learn/what-is-machine-learning",
      "snippet": "Machine learning is a subset of artificial intelligence...",
      "engine": "searxng",
      "content": "Machine learning is a subset of artificial intelligence...",
      "scraped": true
    }
  ],
  "source": "searxng"
}
```

### 6. Intelligence (JARVIS Mode)
```bash
curl -X POST http://localhost:7860/intelligence \
  -H "Content-Type: application/json" \
  -d '{
    "query": "latest AI breakthroughs 2024",
    "lang": "en",
    "max_results": 8,
    "scrape_top": 3,
    "mode": "balanced"
  }'
```

**Response**:
```json
{
  "query": "latest AI breakthroughs 2024",
  "lang": "en",
  "summary": "Recent AI breakthroughs in 2024 include advances in multimodal models, improved reasoning capabilities, and more efficient training methods. Key developments focus on making AI more accessible and practical for real-world applications.",
  "key_points": [
    "Multimodal AI models combining text, image, and video understanding",
    "Improved reasoning and planning capabilities in large language models",
    "More efficient training methods reducing computational requirements",
    "Increased focus on AI safety and alignment research"
  ],
  "sources": [
    {
      "index": 1,
      "title": "AI Breakthroughs 2024",
      "url": "https://example.com/ai-2024",
      "engine": "searxng"
    }
  ],
  "search_source": "searxng",
  "model_used": "llama-3.1-8b-instant",
  "scrape_count": 3
}
```

---

## Language Support

### English Search
```bash
curl -X POST http://localhost:7860/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "lang": "en",
    "max_results": 5
  }'
```

### Hindi Search
```bash
curl -X POST http://localhost:7860/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "कृत्रिम बुद्धिमत्ता",
    "lang": "hi",
    "max_results": 5
  }'
```

### Auto-Detect Language
```bash
curl -X POST http://localhost:7860/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "कृत्रिम बुद्धिमत्ता",
    "lang": "auto",
    "max_results": 5
  }'
```

---

## Performance Testing

### Load Testing with Apache Bench
```bash
# Test search endpoint with 100 requests, 10 concurrent
ab -n 100 -c 10 -p search_payload.json -T application/json http://localhost:7860/search

# Test scrape endpoint
ab -n 50 -c 5 -p scrape_payload.json -T application/json http://localhost:7860/scrape
```

### Rate Limit Testing
```bash
# Send 150 requests (exceeds 120/min limit)
for i in {1..150}; do
  curl -X GET http://localhost:7860/health
done

# Should see 429 Too Many Requests after 120 requests
```

---

## Troubleshooting

### Issue: Crawl4AI Not Available
**Symptom**: Logs show "Crawl4AI not available, using fallback scrapers"

**Solution**:
```bash
# Install crawl4ai
pip install crawl4ai>=0.5.0

# Verify installation
python -c "from crawl4ai import AsyncWebCrawler; print('OK')"
```

### Issue: Playwright Timeout
**Symptom**: Scrape requests timeout after 20 seconds

**Solution**:
- Check target URL accessibility
- Try with `extract_text: false` to skip content extraction
- Check network connectivity
- Increase timeout in code if needed

### Issue: Rate Limit Exceeded
**Symptom**: 429 Too Many Requests response

**Solution**:
- Implement exponential backoff in client
- Reduce request rate to <120/min
- Use caching to avoid duplicate requests
- Wait for rate limit window to reset (60 seconds)

### Issue: Search Returns No Results
**Symptom**: Empty results array

**Solution**:
1. Check if SearXNG is configured and healthy
2. Try different search query
3. Check language setting
4. Verify internet connectivity
5. Check logs for specific errors

### Issue: Groq Summarization Fails
**Symptom**: Intelligence endpoint returns error

**Solution**:
- Verify GROQ_API_KEY is set
- Check API key validity
- Verify API rate limits not exceeded
- Check network connectivity to api.groq.com

---

## Monitoring & Logging

### Enable Debug Logging
```bash
$env:LOG_LEVEL = "DEBUG"
uvicorn deployments.huggingface.scraper-space.main:app --host 0.0.0.0 --port 7860
```

### Log Format
```
2024-05-11 14:30:45 [INFO] tillu.scraper - Search: artificial intelligence (lang=en, max=10, cat=general)
2024-05-11 14:30:46 [INFO] tillu.scraper - SearXNG: artificial intelligence -> 10 results
2024-05-11 14:30:47 [INFO] tillu.scraper - Scraped: https://example.com -> 5234 chars, 42 links
```

### Key Metrics to Monitor
- **Uptime**: Service availability
- **Requests Total**: Total API requests
- **Searches Total**: Total search operations
- **Scrapes Total**: Total scrape operations
- **Intelligence Total**: Total intelligence operations
- **Errors Total**: Total errors
- **Engine Hits**: Breakdown by search engine
- **Cache Hits**: Cache effectiveness
- **Rate Limit Window Count**: Current requests in window

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] No hardcoded secrets in code
- [ ] Environment variables documented
- [ ] Dependencies pinned to specific versions
- [ ] Dockerfile builds successfully
- [ ] README.md updated

### HuggingFace Space Deployment
- [ ] Create new Space: `tillu-ai-tillu-scraper`
- [ ] Set SDK to Docker
- [ ] Upload files:
  - [ ] Dockerfile
  - [ ] main.py
  - [ ] requirements.txt
  - [ ] README.md
- [ ] Configure Space Secrets:
  - [ ] SEARXNG_URL
  - [ ] GROQ_API_KEY (optional)
- [ ] Set LOG_LEVEL to INFO
- [ ] Test health endpoint
- [ ] Test status endpoint
- [ ] Monitor logs for errors

### Post-Deployment
- [ ] Verify health check passes
- [ ] Test all endpoints
- [ ] Monitor error rates
- [ ] Check response times
- [ ] Verify caching works
- [ ] Test rate limiting
- [ ] Monitor resource usage

---

## Performance Benchmarks

### Expected Response Times (Local)
- **Health Check**: <50ms
- **Status Endpoint**: <100ms
- **Search (cached)**: <100ms
- **Search (SearXNG)**: 1-3s
- **Search (DDG)**: 1-2s
- **Scrape (Crawl4AI)**: 2-5s
- **Scrape (Playwright)**: 5-10s
- **Intelligence**: 5-15s (includes search + scrape + LLM)

### Expected Resource Usage
- **Memory**: 200-500MB (idle), 500-1000MB (under load)
- **CPU**: <10% (idle), 50-80% (scraping)
- **Disk**: ~100MB (code + dependencies)

---

## Support & Documentation

- **GitHub**: https://github.com/Heoster/tillu
- **HuggingFace**: https://huggingface.co/spaces/tillu-AI/tillu-scraper
- **Issues**: Report via GitHub Issues
- **Logs**: Check HuggingFace Space logs for deployment issues

---

## Version History

- **v2.0.0** (Current): Renamed to scraper, improved Crawl4AI integration
- **v1.0.0**: Initial release with SearXNG + Playwright

---

## License

MIT License - See LICENSE file for details
