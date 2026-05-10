from __future__ import annotations
import asyncio, logging, os, re, time, hashlib, json
from collections import deque
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse, unquote, urlencode

import httpx
import orjson
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import ORJSONResponse
from langdetect import detect, LangDetectException
from playwright.async_api import async_playwright, Browser, BrowserContext
from pydantic import BaseModel, Field, field_validator
from readability import Document

# Crawl4AI for AI-optimized scraping
try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    logger.warning("Crawl4AI not available, using fallback scrapers")
from tenacity import (
    retry, retry_if_exception_type,
    stop_after_attempt, wait_exponential, before_sleep_log,
)

load_dotenv()
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('tillu.websearch')

SEARXNG_URL: str = os.getenv('SEARXNG_URL', '').rstrip('/')
DDG_JSON_URL = 'https://api.duckduckgo.com/'
DDG_HTML_URL = 'https://html.duckduckgo.com/html/'
DDG_HTML_URL2 = 'https://duckduckgo.com/html/'
GOOGLE_LITE_URL = 'https://www.google.com/search'
GROQ_API_KEY: str | None = os.getenv('GROQ_API_KEY')
GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL = 'llama-3.1-8b-instant'

# ---------------------------------------------------------------------------
# Rate limiter - sliding window
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def check(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_requests:
                return False
            self._timestamps.append(now)
            return True

    @property
    def current_count(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window
        return sum(1 for t in self._timestamps if t >= cutoff)

rate_limiter = RateLimiter()

# ---------------------------------------------------------------------------
# Service stats
# ---------------------------------------------------------------------------
class ServiceStats:
    def __init__(self) -> None:
        self.start_time = time.time()
        self.requests_total: int = 0
        self.searches_total: int = 0
        self.scrapes_total: int = 0
        self.intelligence_total: int = 0
        self.errors_total: int = 0
        self.searxng_hits: int = 0
        self.ddg_hits: int = 0
        self.google_hits: int = 0
        self.cache_hits: int = 0

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            'uptime_seconds': round(self.uptime_seconds, 1),
            'requests_total': self.requests_total,
            'searches_total': self.searches_total,
            'scrapes_total': self.scrapes_total,
            'intelligence_total': self.intelligence_total,
            'errors_total': self.errors_total,
            'engine_hits': {
                'searxng': self.searxng_hits,
                'duckduckgo': self.ddg_hits,
                'google': self.google_hits,
            },
            'cache_hits': self.cache_hits,
            'rate_limit_window_count': rate_limiter.current_count,
        }

stats = ServiceStats()

# ---------------------------------------------------------------------------
# Search result cache (TTL 5 min)
# ---------------------------------------------------------------------------
_search_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 300

def _cache_key(query: str, lang: str, n: int) -> str:
    return hashlib.md5(f'{query}:{lang}:{n}'.encode()).hexdigest()

def _cache_get(key: str) -> Any | None:
    entry = _search_cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None

def _cache_set(key: str, value: Any) -> None:
    _search_cache[key] = (time.time(), value)
    if len(_search_cache) > 500:
        cutoff = time.time() - CACHE_TTL
        for k in [k for k, (t, _) in list(_search_cache.items()) if t < cutoff]:
            _search_cache.pop(k, None)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
HINDI_RE = re.compile(r'[ऀ-ॿ]')

def detect_language(text: str) -> str:
    if HINDI_RE.search(text):
        return 'hi'
    try:
        return 'hi' if detect(text) == 'hi' else 'en'
    except LangDetectException:
        return 'en'

def resolve_lang(lang: str, query: str) -> str:
    return detect_language(query) if lang == 'auto' else lang

# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------
_http: httpx.AsyncClient | None = None

def get_http() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
            },
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
        )
    return _http

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    engine: str = 'unknown'
    score: float = 1.0
    content: str | None = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    lang: str = Field('auto', description='hi | en | auto')
    max_results: int = Field(10, ge=1, le=50)
    scrape_content: bool = Field(False)
    categories: str = Field('general', description='general | news | science | it')

    @field_validator('lang')
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if v not in ('hi', 'en', 'auto'):
            raise ValueError('lang must be hi, en, or auto')
        return v

class ScrapeRequest(BaseModel):
    url: str = Field(..., description='URL to scrape')
    extract_text: bool = Field(True)

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        p = urlparse(v)
        if p.scheme not in ('http', 'https'):
            raise ValueError('URL must use http or https')
        return v

class SearchAndScrapeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    lang: str = Field('auto')
    max_results: int = Field(10, ge=1, le=50)
    scrape_top: int = Field(3, ge=1, le=10)
    categories: str = Field('general')

    @field_validator('lang')
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if v not in ('hi', 'en', 'auto'):
            raise ValueError('lang must be hi, en, or auto')
        return v

class IntelligenceRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    lang: str = Field('auto')
    max_results: int = Field(8, ge=1, le=20)
    scrape_top: int = Field(3, ge=1, le=5)
    mode: str = Field('balanced', description='fast | balanced | deep')

    @field_validator('lang')
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if v not in ('hi', 'en', 'auto'):
            raise ValueError('lang must be hi, en, or auto')
        return v

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ('fast', 'balanced', 'deep'):
            raise ValueError('mode must be fast, balanced, or deep')
        return v

class ScrapeResponse(BaseModel):
    url: str
    title: str
    text: str
    links: list[str]
    success: bool
    error: str | None = None

class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    lang: str
    total: int
    source: str
    cached: bool = False

class SearchAndScrapeResult(BaseModel):
    title: str
    url: str
    snippet: str
    engine: str = 'unknown'
    content: str | None = None
    scraped: bool = False

class SearchAndScrapeResponse(BaseModel):
    query: str
    lang: str
    results: list[SearchAndScrapeResult]
    source: str

class IntelligenceResponse(BaseModel):
    query: str
    lang: str
    summary: str
    key_points: list[str]
    sources: list[dict]
    search_source: str
    model_used: str
    scrape_count: int

_browser = None
_pw = None

async def get_browser():
    global _browser, _pw
    if _browser is None or not _browser.is_connected():
        logger.info('Playwright: starting Chromium')
        _pw = await async_playwright().start()
        _browser = await _pw.chromium.launch(
            headless=True,
            args=['--no-sandbox','--disable-setuid-sandbox',
                  '--disable-dev-shm-usage','--disable-gpu',
                  '--no-first-run','--no-zygote','--single-process',
                  '--disable-extensions'],
        )
        logger.info('Playwright: ready')
    return _browser

async def close_browser():
    global _browser, _pw
    if _browser:
        await _browser.close()
        _browser = None
    if _pw:
        await _pw.stop()
        _pw = None

@asynccontextmanager
async def lifespan(app):
    logger.info('TILLU WebSearch v2 starting')
    logger.info('SearXNG: ' + (SEARXNG_URL or 'NOT SET - DDG fallback active'))
    logger.info('Groq: ' + ('configured' if GROQ_API_KEY else 'not set'))
    await get_browser()
    yield
    await close_browser()

app = FastAPI(
    title='TILLU WebSearch v2',
    description='JARVIS-grade search + scrape + intelligence',
    version='2.0.0',
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# SearXNG search (primary)
# ---------------------------------------------------------------------------
@retry(retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
       stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4),
       before_sleep=before_sleep_log(logger, logging.WARNING), reraise=True)
async def search_searxng(query: str, lang: str, max_results: int, categories: str = 'general') -> list[SearchResult]:
    if not SEARXNG_URL:
        raise ValueError('SEARXNG_URL not configured')
    params = {
        'q': query,
        'format': 'json',
        'language': lang,
        'categories': categories,
        'pageno': 1,
    }
    client = get_http()
    resp = await client.get(SEARXNG_URL + '/search', params=params, timeout=12.0)
    resp.raise_for_status()
    data = resp.json()
    raw = data.get('results', [])
    results = []
    for r in raw[:max_results]:
        results.append(SearchResult(
            title=r.get('title', ''),
            url=r.get('url', ''),
            snippet=r.get('content', r.get('snippet', '')),
            engine=','.join(r.get('engines', ['searxng'])),
            score=float(r.get('score', 1.0)),
        ))
    logger.info('SearXNG: %s -> %d results', query, len(results))
    return results

# ---------------------------------------------------------------------------
# DuckDuckGo JSON fallback
# ---------------------------------------------------------------------------
async def search_ddg_json(query: str, lang: str, max_results: int) -> list[SearchResult]:
    params = {
        'q': query,
        'format': 'json',
        'no_html': '1',
        'skip_disambig': '1',
        'kl': 'in-hi' if lang == 'hi' else 'us-en',
    }
    client = get_http()
    try:
        resp = await client.get(DDG_JSON_URL, params=params, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        results = []
        # Instant answer
        if data.get('AbstractText'):
            results.append(SearchResult(
                title=data.get('Heading', query),
                url=data.get('AbstractURL', ''),
                snippet=data.get('AbstractText', '')[:400],
                engine='duckduckgo_instant',
            ))
        # Related topics
        for topic in data.get('RelatedTopics', [])[:max_results]:
            if isinstance(topic, dict) and topic.get('FirstURL'):
                results.append(SearchResult(
                    title=topic.get('Text', '')[:80],
                    url=topic.get('FirstURL', ''),
                    snippet=topic.get('Text', '')[:300],
                    engine='duckduckgo',
                ))
        if results:
            logger.info('DDG JSON: %s -> %d results', query, len(results))
            return results[:max_results]
    except Exception as e:
        logger.warning('DDG JSON failed: %s', e)
    # Fall through to HTML scrape
    return await search_ddg_html(query, lang, max_results)

async def search_ddg_html(query: str, lang: str, max_results: int) -> list[SearchResult]:
    params = {
        'q': query,
        'kl': 'in-hi' if lang == 'hi' else 'us-en',
        'kp': '-2',
        'k1': '-1',
    }
    client = get_http()
    try:
        resp = await client.post(
            DDG_HTML_URL,
            data=params,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=12.0,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        results = []
        # Try multiple selector patterns (DDG changes HTML periodically)
        selectors = [
            ('.result__body', '.result__title a', '.result__snippet'),
            ('.results_links', '.result__a', '.result__snippet'),
            ('.web-result', '.result__title a', '.result__snippet'),
        ]
        for body_sel, title_sel, snip_sel in selectors:
            for div in soup.select(body_sel)[:max_results]:
                t = div.select_one(title_sel)
                s = div.select_one(snip_sel)
                if not t:
                    continue
                raw_url = t.get('href', '')
                url = _extract_ddg_url(raw_url)
                if url:
                    results.append(SearchResult(
                        title=t.get_text(strip=True),
                        url=url,
                        snippet=s.get_text(strip=True) if s else '',
                        engine='duckduckgo_html',
                    ))
            if results:
                break
        logger.info('DDG HTML: %s -> %d results', query, len(results))
        return results
    except Exception as e:
        logger.warning('DDG HTML failed: %s', e)
        return []

def _extract_ddg_url(raw: str) -> str:
    if not raw:
        return ''
    if 'uddg=' in raw:
        m = re.search(r'uddg=([^&]+)', raw)
        if m:
            return unquote(m.group(1))
    if raw.startswith('http'):
        return raw
    return ''

# ---------------------------------------------------------------------------
# Google Lite fallback (last resort)
# ---------------------------------------------------------------------------
async def search_google_lite(query: str, lang: str, max_results: int) -> list[SearchResult]:
    params = {
        'q': query,
        'hl': 'hi' if lang == 'hi' else 'en',
        'gl': 'in' if lang == 'hi' else 'us',
        'num': min(max_results, 10),
    }
    client = get_http()
    try:
        resp = await client.get(
            GOOGLE_LITE_URL,
            params=params,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
                'Accept-Language': 'hi-IN,hi;q=0.9,en;q=0.8' if lang == 'hi' else 'en-US,en;q=0.9',
            },
            timeout=12.0,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        results = []
        for g in soup.select('div.g, div[data-sokoban-container]')[:max_results]:
            a = g.select_one('a[href]')
            h3 = g.select_one('h3')
            snip = g.select_one('div[data-sncf], span.aCOpRe, div.VwiC3b')
            if not a or not h3:
                continue
            href = a.get('href', '')
            if href.startswith('/url?q='):
                href = href[7:].split('&')[0]
            if not href.startswith('http'):
                continue
            results.append(SearchResult(
                title=h3.get_text(strip=True),
                url=href,
                snippet=snip.get_text(strip=True)[:300] if snip else '',
                engine='google_lite',
            ))
        logger.info('Google Lite: %s -> %d results', query, len(results))
        return results
    except Exception as e:
        logger.warning('Google Lite failed: %s', e)
        return []

# ---------------------------------------------------------------------------
# Bing search fallback
# ---------------------------------------------------------------------------
async def search_bing(query: str, lang: str, max_results: int) -> list[SearchResult]:
    """Bing web search — different IP reputation than Google/DDG."""
    params = {
        'q': query,
        'setlang': 'hi' if lang == 'hi' else 'en',
        'cc': 'IN' if lang == 'hi' else 'US',
        'count': min(max_results, 10),
    }
    client = get_http()
    try:
        resp = await client.get(
            'https://www.bing.com/search',
            params=params,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept-Language': 'hi-IN,hi;q=0.9,en;q=0.8' if lang == 'hi' else 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml',
            },
            timeout=12.0,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')
        results = []
        for li in soup.select('li.b_algo')[:max_results]:
            a = li.select_one('h2 a')
            snip = li.select_one('.b_caption p, .b_algoSlug')
            if not a:
                continue
            href = a.get('href', '')
            if not href.startswith('http'):
                continue
            results.append(SearchResult(
                title=a.get_text(strip=True),
                url=href,
                snippet=snip.get_text(strip=True)[:300] if snip else '',
                engine='bing',
            ))
        logger.info('Bing: %s -> %d results', query, len(results))
        return results
    except Exception as e:
        logger.warning('Bing failed: %s', e)
        return []


# ---------------------------------------------------------------------------
# Groq LLM knowledge search (works when all web search is blocked)
# ---------------------------------------------------------------------------
async def search_groq_knowledge(query: str, lang: str, max_results: int) -> list[SearchResult]:
    """
    Use Groq LLM to generate search results from its training knowledge.
    Last resort when all web search engines are blocked.
    Returns results with source='groq_knowledge' and no real URLs.
    """
    if not GROQ_API_KEY:
        return []

    lang_instruction = 'Respond in Hindi (Devanagari script) mixed with English (Hinglish).' if lang == 'hi' else 'Respond in English.'
    prompt = f"""You are a search engine. The user searched for: "{query}"

{lang_instruction}

Return exactly {min(max_results, 5)} search results as a JSON array. Each result must have:
- "title": descriptive title
- "url": a plausible URL (can be approximate)
- "snippet": 1-2 sentence summary

Return ONLY the JSON array, no other text:
[{{"title": "...", "url": "...", "snippet": "..."}}]"""

    client = get_http()
    try:
        resp = await client.post(
            GROQ_API_URL,
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 800,
                'temperature': 0.3,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content'].strip()
        # Extract JSON array
        start = content.find('[')
        end = content.rfind(']') + 1
        if start < 0 or end <= start:
            return []
        items = json.loads(content[start:end])
        results = []
        for item in items[:max_results]:
            results.append(SearchResult(
                title=item.get('title', ''),
                url=item.get('url', 'https://tillu.ai/knowledge'),
                snippet=item.get('snippet', ''),
                engine='groq_knowledge',
            ))
        logger.info('Groq knowledge: %s -> %d results', query, len(results))
        return results
    except Exception as e:
        logger.warning('Groq knowledge search failed: %s', e)
        return []


# ---------------------------------------------------------------------------
# Unified search with fallback chain
# ---------------------------------------------------------------------------
async def do_search(
    query: str,
    lang: str,
    max_results: int,
    categories: str = 'general',
) -> tuple[list[SearchResult], str]:
    key = _cache_key(query, lang, max_results)
    cached = _cache_get(key)
    if cached is not None:
        stats.cache_hits += 1
        logger.info('Cache hit: %s', query)
        return cached, 'cache'

    # 1. SearXNG (primary)
    if SEARXNG_URL:
        try:
            results = await search_searxng(query, lang, max_results, categories)
            if results:
                stats.searxng_hits += 1
                _cache_set(key, results)
                return results, 'searxng'
            logger.warning('SearXNG returned 0 results, falling back')
        except Exception as e:
            logger.warning('SearXNG failed: %s - falling back to DDG', e)

    # 2. DuckDuckGo JSON -> HTML
    try:
        results = await search_ddg_json(query, lang, max_results)
        if results:
            stats.ddg_hits += 1
            _cache_set(key, results)
            return results, 'duckduckgo'
        logger.warning('DDG returned 0 results, falling back to Google Lite')
    except Exception as e:
        logger.warning('DDG failed: %s - falling back to Google Lite', e)

    # 3. Google Lite (last resort)
    results = await search_google_lite(query, lang, max_results)
    if results:
        stats.google_hits += 1
        _cache_set(key, results)
        return results, 'google_lite'

    # 4. Bing (final fallback — different IP reputation than Google/DDG)
    results = await search_bing(query, lang, max_results)
    if results:
        stats.google_hits += 1  # reuse counter
        _cache_set(key, results)
        return results, 'bing'

    # 5. Groq LLM knowledge search (works even when all web search is blocked)
    if GROQ_API_KEY:
        results = await search_groq_knowledge(query, lang, max_results)
        if results:
            _cache_set(key, results)
            return results, 'groq_knowledge'

    return [], 'none'

# ---------------------------------------------------------------------------
# Crawl4AI scraper (Primary - AI-optimized)
# ---------------------------------------------------------------------------
async def scrape_with_crawl4ai(url: str) -> ScrapeResponse:
    """Scrape using Crawl4AI - optimized for AI/LLM applications"""
    if not CRAWL4AI_AVAILABLE:
        raise RuntimeError("Crawl4AI not available")
    
    try:
        # Configure browser for lightweight scraping
        browser_config = BrowserConfig(
            headless=True,
            text_mode=True,  # Skip images for speed
            light_mode=True,  # Reduce memory usage
        )
        
        run_config = CrawlerRunConfig(
            word_count_threshold=10,  # Filter out short fragments
            remove_overlay_elements=True,  # Remove popups/modals
            excluded_tags=['script', 'style', 'nav', 'footer', 'header'],
        )
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)
            
            return ScrapeResponse(
                url=str(result.url),
                title=result.metadata.get('title', ''),
                content=result.markdown or result.cleaned_text or result.text,
                html=None,  # Crawl4AI returns markdown by default
                text=result.cleaned_text or result.text,
                status=200,
                scrape_method='crawl4ai',
                links=[],
                metadata={
                    'crawl4ai_success': result.success,
                    'links_found': len(result.links.get('internal', [])) + len(result.links.get('external', [])),
                    'images_found': len(result.media.get('images', [])),
                }
            )
    except Exception as e:
        logger.error(f"Crawl4AI scrape failed for {url}: {e}")
        raise


# ---------------------------------------------------------------------------
# Playwright scraper (Fallback)
# ---------------------------------------------------------------------------
async def scrape_url(url: str, extract_text: bool = True) -> ScrapeResponse:
    browser = await get_browser()
    ctx = None
    try:
        ctx = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={'Accept-Language': 'hi-IN,hi;q=0.9,en-US,en;q=0.8'},
        )
        page = await ctx.new_page()

        async def block_heavy(route):
            if route.request.resource_type in ('image', 'media', 'font', 'stylesheet', 'websocket'):
                await route.abort()
            else:
                await route.continue_()

        await page.route('**/*', block_heavy)
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(1200)

        title = await page.title()
        html = await page.content()

        links_raw = await page.eval_on_selector_all(
            'a[href]',
            'els => els.map(e => e.href).filter(h => h.startsWith(' + chr(39) + 'http' + chr(39) + '))',
        )
        links = list(dict.fromkeys(links_raw))[:50]
        text = _extract_readable(html, url) if extract_text else ''
        logger.info('Scraped: %s -> %d chars, %d links', url, len(text), len(links))
        return ScrapeResponse(url=url, title=title, text=text, links=links, success=True)

    except Exception as e:
        logger.error('Scrape failed for %s: %s', url, e)
        return ScrapeResponse(url=url, title='', text='', links=[], success=False, error=str(e))
    finally:
        if ctx:
            await ctx.close()

def _extract_readable(html: str, url: str) -> str:
    try:
        doc = Document(html)
        summary = doc.summary(html_partial=True)
        soup = BeautifulSoup(summary, 'lxml')
        text = soup.get_text(separator=chr(10), strip=True)
        text = re.sub(r' chr(10) {3,}', chr(10)+chr(10), text)
        return text.strip()
    except Exception as e:
        logger.warning('readability failed for %s: %s', url, e)
        soup = BeautifulSoup(html, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        return soup.get_text(separator=chr(10), strip=True)[:12000]

# ---------------------------------------------------------------------------
# Groq LLM summariser for /intelligence
# ---------------------------------------------------------------------------
async def groq_summarise(query: str, context: str, lang: str) -> tuple[str, list[str]]:
    if not GROQ_API_KEY:
        # Fallback: extract first 3 sentences per source
        lines = [l.strip() for l in context.split(chr(10)) if len(l.strip()) > 40][:6]
        return chr(10).join(lines), lines[:3]

    lang_instruction = 'Respond in Hindi.' if lang == 'hi' else 'Respond in English.'
    system_prompt = (
        'You are TILLU, a JARVIS-like AI assistant. '
        'Synthesise the provided search results into a clear, accurate, concise answer. '
        'Always cite sources with [1], [2] etc. '
        + lang_instruction
    )
    user_prompt = (
        'Query: ' + query + chr(10) + chr(10) +
        'Search results:' + chr(10) + context[:6000] + chr(10) + chr(10) +
        'Provide: 1) A 3-5 sentence summary. 2) 3-5 key bullet points. '
        'Format: SUMMARY: <text> KEY_POINTS: - point1 - point2 ...'
    )

    client = get_http()
    try:
        resp = await client.post(
            GROQ_API_URL,
            headers={'Authorization': 'Bearer ' + GROQ_API_KEY, 'Content-Type': 'application/json'},
            json={
                'model': GROQ_MODEL,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'max_tokens': 800,
                'temperature': 0.3,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data['choices'][0]['message']['content']

        summary = text
        key_points = []
        if 'SUMMARY:' in text:
            parts = text.split('KEY_POINTS:')
            summary = parts[0].replace('SUMMARY:', '').strip()
            if len(parts) > 1:
                key_points = [
                    p.strip().lstrip('-').strip()
                    for p in parts[1].split(chr(10))
                    if p.strip().startswith('-')
                ]
        return summary, key_points[:6]

    except Exception as e:
        logger.error('Groq summarise failed: %s', e)
        lines = [l.strip() for l in context.split(chr(10)) if len(l.strip()) > 40][:4]
        return chr(10).join(lines), lines[:3]

# ---------------------------------------------------------------------------
# Rate-limit middleware
# ---------------------------------------------------------------------------
@app.middleware('http')
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ('/health', '/status'):
        return await call_next(request)
    allowed = await rate_limiter.check()
    if not allowed:
        stats.errors_total += 1
        return ORJSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={'error': 'Rate limit exceeded', 'detail': 'Max 120 requests per minute'},
        )
    stats.requests_total += 1
    return await call_next(request)

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get('/health', response_class=ORJSONResponse)
async def health():
    return {'status': 'ok', 'service': 'tillu-websearch', 'version': '2.0.0'}

@app.get('/status', response_class=ORJSONResponse)
async def service_status():
    searxng_ok = False
    if SEARXNG_URL:
        try:
            r = await get_http().get(SEARXNG_URL + '/healthz', timeout=3.0)
            searxng_ok = r.status_code == 200
        except Exception:
            searxng_ok = False
    return {
        'service': 'tillu-websearch',
        'version': '2.0.0',
        'engines': {
            'searxng': {'url': SEARXNG_URL or 'not configured', 'healthy': searxng_ok},
            'duckduckgo': {'status': 'fallback'},
            'google_lite': {'status': 'last_resort'},
        },
        'groq_configured': bool(GROQ_API_KEY),
        'cache_size': len(_search_cache),
        **stats.to_dict(),
    }

@app.post('/search', response_model=SearchResponse, response_class=ORJSONResponse)
async def search(req: SearchRequest):
    stats.searches_total += 1
    lang = resolve_lang(req.lang, req.query)
    logger.info('Search: %s (lang=%s, max=%d, cat=%s)', req.query, lang, req.max_results, req.categories)

    try:
        results, source = await do_search(req.query, lang, req.max_results, req.categories)
    except Exception as e:
        stats.errors_total += 1
        raise HTTPException(status_code=502, detail='Search failed: ' + str(e))

    cached = source == 'cache'

    if req.scrape_content and results:
        tasks = [scrape_url(r.url) for r in results[:5]]
        scraped = await asyncio.gather(*tasks, return_exceptions=True)
        for result, sd in zip(results[:5], scraped):
            if isinstance(sd, ScrapeResponse) and sd.success:
                result.content = sd.text[:5000]

    return SearchResponse(
        results=results, query=req.query, lang=lang,
        total=len(results), source=source, cached=cached,
    )

@app.post('/scrape', response_model=ScrapeResponse, response_class=ORJSONResponse)
async def scrape(req: ScrapeRequest):
    """Scrape endpoint with Crawl4AI as primary, Playwright as fallback"""
    stats.scrapes_total += 1
    logger.info('Scrape: %s', req.url)
    
    # Try Crawl4AI first (AI-optimized, lighter than Playwright)
    if CRAWL4AI_AVAILABLE:
        try:
            return await scrape_with_crawl4ai(req.url)
        except Exception as e:
            logger.warning(f"Crawl4AI failed, falling back to Playwright: {e}")
    
    # Fallback to Playwright
    return await scrape_url(req.url, req.extract_text)

@app.post('/search-and-scrape', response_model=SearchAndScrapeResponse, response_class=ORJSONResponse)
async def search_and_scrape(req: SearchAndScrapeRequest):
    stats.searches_total += 1
    lang = resolve_lang(req.lang, req.query)
    logger.info('Search+Scrape: %s (lang=%s, scrape_top=%d)', req.query, lang, req.scrape_top)

    try:
        search_results, source = await do_search(req.query, lang, req.max_results, req.categories)
    except Exception as e:
        stats.errors_total += 1
        raise HTTPException(status_code=502, detail='Search failed: ' + str(e))

    to_scrape = search_results[:req.scrape_top]
    rest = search_results[req.scrape_top:]

    scrape_tasks = [scrape_url(r.url) for r in to_scrape]
    scraped_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

    combined: list[SearchAndScrapeResult] = []
    for sr, sd in zip(to_scrape, scraped_results):
        content = None
        scraped = False
        if isinstance(sd, ScrapeResponse) and sd.success:
            content = sd.text[:5000]
            scraped = True
            stats.scrapes_total += 1
        combined.append(SearchAndScrapeResult(
            title=sr.title, url=sr.url, snippet=sr.snippet,
            engine=sr.engine, content=content, scraped=scraped,
        ))
    for sr in rest:
        combined.append(SearchAndScrapeResult(
            title=sr.title, url=sr.url, snippet=sr.snippet,
            engine=sr.engine, content=None, scraped=False,
        ))

    return SearchAndScrapeResponse(query=req.query, lang=lang, results=combined, source=source)

@app.post('/intelligence', response_model=IntelligenceResponse, response_class=ORJSONResponse)
async def intelligence(req: IntelligenceRequest):
    stats.intelligence_total += 1
    lang = resolve_lang(req.lang, req.query)
    logger.info('Intelligence: %s (lang=%s, mode=%s)', req.query, lang, req.mode)

    # Step 1: search
    try:
        search_results, source = await do_search(req.query, lang, req.max_results)
    except Exception as e:
        stats.errors_total += 1
        raise HTTPException(status_code=502, detail='Search failed: ' + str(e))

    if not search_results:
        raise HTTPException(status_code=404, detail='No search results found for: ' + req.query)

    # Step 2: scrape top-N concurrently
    scrape_n = req.scrape_top if req.mode != 'fast' else 1
    to_scrape = search_results[:scrape_n]
    scrape_tasks = [scrape_url(r.url) for r in to_scrape]
    scraped = await asyncio.gather(*scrape_tasks, return_exceptions=True)

    # Step 3: build context for LLM
    context_parts = []
    sources_out = []
    scrape_count = 0

    for i, (sr, sd) in enumerate(zip(to_scrape, scraped), 1):
        content = sr.snippet
        if isinstance(sd, ScrapeResponse) and sd.success and sd.text:
            content = sd.text[:2000]
            scrape_count += 1
            stats.scrapes_total += 1
        context_parts.append('[' + str(i) + '] ' + sr.title + chr(10) + 'URL: ' + sr.url + chr(10) + content[:1500])
        sources_out.append({'index': i, 'title': sr.title, 'url': sr.url, 'engine': sr.engine})

    # Add remaining results as snippets only
    for i, sr in enumerate(search_results[scrape_n:req.max_results], scrape_n + 1):
        context_parts.append('[' + str(i) + '] ' + sr.title + chr(10) + 'URL: ' + sr.url + chr(10) + sr.snippet[:400])
        sources_out.append({'index': i, 'title': sr.title, 'url': sr.url, 'engine': sr.engine})

    context = chr(10) + chr(10).join(context_parts)

    # Step 4: LLM summarise
    summary, key_points = await groq_summarise(req.query, context, lang)

    model_used = GROQ_MODEL if GROQ_API_KEY else 'extractive_fallback'

    return IntelligenceResponse(
        query=req.query,
        lang=lang,
        summary=summary,
        key_points=key_points,
        sources=sources_out,
        search_source=source,
        model_used=model_used,
        scrape_count=scrape_count,
    )

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    stats.errors_total += 1
    logger.error('Unhandled exception on %s: %s', request.url.path, exc, exc_info=True)
    return ORJSONResponse(
        status_code=500,
        content={'error': 'Internal server error', 'detail': str(exc)},
    )
