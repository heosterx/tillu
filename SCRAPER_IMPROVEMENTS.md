# TILLU Scraper v2 - Improvements & Deployment Guide

## Overview
The TILLU Scraper (formerly WebSearch) is a JARVIS-grade unified web search, scraping, and AI intelligence service. It combines multiple search engines with intelligent scraping and LLM-powered summarization.

**Latest Commit**: `7983eee` - Renamed websearch-space to scraper-space with improved implementation

## Key Improvements (Latest Update)

### 1. **Renamed to "Scraper"**
- Directory: `deployments/huggingface/websearch-space/` → `deployments/huggingface/scraper-space/`
- HuggingFace Space: `tillu-ai-tillu-websearch` → `tillu-ai-tillu-scraper`
- Service name: `tillu-websearch` → `tillu-scraper`
- Logger: `tillu.websearch` → `tillu.scraper`

### 2. **Improved Crawl4AI Integration**
- Fixed response model handling to match `ScrapeResponse` schema
- Added proper link extraction from Crawl4AI results
- Implemented content limiting (12k chars) for performance
- Added metadata tracking (links found, content length)
- Graceful fallback to Playwright if Crawl4AI fails

### 3. **Enhanced Playwright Scraper**
- Added timeout handling with graceful degradation
- Improved resource cleanup (page and context closing)
- Better error handling with try-catch blocks
- Added `scrape_method` tracking for debugging
- Prevents resource leaks on failures

### 4. **Updated ScrapeResponse Model**
```python
class ScrapeResponse(BaseModel):
    url: str
    title: str
    text: str
    links: list[str] = []
    success: bool
    error: str | None = None
    scrape_method: str = 'unknown'  # NEW: tracks which scraper was used
    metadata: dict[str, Any] = {}   # NEW: additional scraper info
```

### 5. **Enhanced Status Endpoint**
The `/status` endpoint now includes scraper availability:
```json
{
  "scrapers": {
    "crawl4ai": {"available": true, "type": "primary"},
    "playwright": {"available": true, "type": "fallback"}
  }
}
```

## Architecture

### Search Chain (Automatic Fallback)
1. **SearXNG** (primary) - Meta-search: Google, Bing, DDG, Wikipedia, Reddit, GitHub, ArXiv
2. **DuckDuckGo JSON** (fallback) - Instant answers
3. **DuckDuckGo HTML** (fallback) - Full HTML scrape
4. **Google Lite** (last resort) - Lightweight Google search
5. **Bing** (final fallback) - Different IP reputation
6. **Groq LLM Knowledge** (emergency) - Works when all web search blocked

### Scraper Chain
1. **Crawl4AI** (primary) - AI-optimized, lightweight, markdown extraction
2. **Playwright** (fallback) - Full browser automation for complex pages

### Features
- **Rate Limiting**: 120 requests/minute (sliding window)
- **Search Caching**: 5-minute TTL, 500-entry limit
- **Language Detection**: Hindi/English auto-detection
- **LLM Summarization**: Groq integration for /intelligence endpoint
- **Service Stats**: Uptime, request counts, engine hits, cache stats

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe |
| GET | `/status` | Engine health + stats |
| POST | `/search` | Web search with fallback chain |
| POST | `/scrape` | Crawl4AI + Playwright fallback |
| POST | `/search-and-scrape` | Search + scrape top-N |
| POST | `/intelligence` | JARVIS mode: search + scrape + AI summary |

## Deployment

### HuggingFace Space Setup
1. Create new Space: `tillu-ai-tillu-scraper`
2. SDK: Docker
3. Copy files:
   - `Dockerfile`
   - `main.py`
   - `requirements.txt`
   - `README.md`

### Space Secrets Configuration
| Secret | Required | Description |
|--------|----------|-------------|
| SEARXNG_URL | Recommended | `https://tillu-ai-tillu-searxng.hf.space` |
| GROQ_API_KEY | Optional | Enables AI summarisation in /intelligence |

### Environment Variables
- `LOG_LEVEL`: INFO (default) | DEBUG | WARNING | ERROR
- `PORT`: 7860 (default for HF Spaces)
- `PLAYWRIGHT_BROWSERS_PATH`: `/home/tillu/.cache/ms-playwright`

## Dependencies

### Core
- `fastapi==0.129.0` - Web framework
- `uvicorn[standard]==0.46.0` - ASGI server
- `httpx==0.28.1` - Async HTTP client

### Scraping
- `playwright==1.48.0` - Browser automation
- `crawl4ai>=0.5.0` - AI-optimized scraping
- `beautifulsoup4==4.13.1` - HTML parsing
- `lxml==5.3.0` - XML/HTML processing
- `readability-lxml==0.8.1` - Content extraction

### Utilities
- `python-dotenv==1.0.1` - Environment config
- `tenacity==9.0.0` - Retry logic
- `orjson==3.10.7` - Fast JSON
- `langdetect==1.0.9` - Language detection

## Performance Characteristics

### Search Performance
- **SearXNG**: ~1-3s (depends on backend)
- **DDG JSON**: ~1-2s
- **DDG HTML**: ~2-4s
- **Google Lite**: ~2-4s
- **Bing**: ~2-4s
- **Cache Hit**: <100ms

### Scraping Performance
- **Crawl4AI**: ~2-5s (AI-optimized, lightweight)
- **Playwright**: ~5-10s (full browser, more reliable)
- **Content Limit**: 12,000 characters (optimized for LLMs)

### Rate Limiting
- **Max Requests**: 120 per minute
- **Window**: Sliding 60-second window
- **Response**: 429 Too Many Requests when exceeded

## Monitoring

### Health Checks
```bash
curl http://localhost:7860/health
# {"status": "ok", "service": "tillu-scraper", "version": "2.0.0"}
```

### Service Status
```bash
curl http://localhost:7860/status
# Returns detailed engine health, scraper availability, and stats
```

### Logs
- Format: `[TIMESTAMP] [LEVEL] logger_name - message`
- Levels: DEBUG, INFO, WARNING, ERROR
- Configure via `LOG_LEVEL` env var

## Example Usage

### Search
```bash
curl -X POST http://localhost:7860/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "artificial intelligence",
    "lang": "en",
    "max_results": 10,
    "scrape_content": false,
    "categories": "general"
  }'
```

### Scrape
```bash
curl -X POST http://localhost:7860/scrape \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "extract_text": true
  }'
```

### Intelligence (JARVIS Mode)
```bash
curl -X POST http://localhost:7860/intelligence \
  -H "Content-Type: application/json" \
  -d '{
    "query": "latest AI breakthroughs",
    "lang": "en",
    "max_results": 8,
    "scrape_top": 3,
    "mode": "balanced"
  }'
```

## Troubleshooting

### Crawl4AI Not Available
- Falls back to Playwright automatically
- Check logs: `Crawl4AI not available, using fallback scrapers`
- Ensure `crawl4ai>=0.5.0` is installed

### Rate Limit Exceeded
- Response: `429 Too Many Requests`
- Limit: 120 requests per 60 seconds
- Implement exponential backoff in client

### Search Returns No Results
- Fallback chain automatically tries next engine
- Check SEARXNG_URL if configured
- Groq knowledge search activates as last resort

### Playwright Timeout
- Page load timeout: 20 seconds
- Continues with partial content if timeout
- Check logs for specific URL issues

## Future Enhancements

1. **Distributed Caching**: Redis for multi-instance deployments
2. **Advanced Filtering**: Content type, date range, domain filters
3. **Custom Scrapers**: User-defined extraction rules
4. **Analytics**: Detailed query and performance analytics
5. **Webhook Support**: Async scraping with callbacks
6. **Proxy Support**: Rotate proxies for reliability
7. **JavaScript Rendering**: Enhanced JS execution options

## Git History

- **7983eee**: Rename websearch-space to scraper-space with improvements
- **Previous**: Docker build fixes, dependency resolution, import updates

## Support

For issues or questions:
1. Check logs: `LOG_LEVEL=DEBUG`
2. Review `/status` endpoint for engine health
3. Test individual endpoints with curl
4. Check HuggingFace Space logs if deployed there
