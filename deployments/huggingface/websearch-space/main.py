"""
TILLU WebSearch Service — Unified Search + Scrape
==================================================
Replaces: tillu-search (SearXNG) + tillu-scraper (Playwright)

Endpoints:
  GET  /health            — liveness probe
  GET  /status            — service stats
  POST /search            — web search (Brave API → DuckDuckGo fallback)
  POST /scrape            — single-URL Playwright scrape
  POST /search-and-scrape — search then scrape top-N results

Environment variables:
  BRAVE_API_KEY           — Brave Search subscription token (optional, enables Brave)
  LOG_LEVEL               — DEBUG | INFO | WARNING (default: INFO)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import unicodedata
from collections import deque
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import orjson
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import ORJSONResponse
from langdetect import detect, LangDetectException
from playwright.async_api import async_playwright, Browser, BrowserContext
from pydantic import BaseModel, Field, HttpUrl, field_validator
from readability import Document
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tillu.websearch")

BRAVE_API_KEY: str | None = os.getenv("BRAVE_API_KEY")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
DDG_HTML_URL = "https://html.duckduckgo.com/html/"

# ---------------------------------------------------------------------------
# Rate limiter — simple sliding-window in-memory counter
# ---------------------------------------------------------------------------

class RateLimiter:
    """100 requests per 60-second window, per service (global)."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def check(self) -> bool:
        """Return True if request is allowed, False if rate-limited."""
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
        self.errors_total: int = 0
        self.brave_hits: int = 0
        self.ddg_hits: int = 0

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "uptime_seconds": round(self.uptime_seconds, 1),
            "requests_total": self.requests_total,
            "searches_total": self.searches_total,
            "scrapes_total": self.scrapes_total,
            "errors_total": self.errors_total,
            "brave_hits": self.brave_hits,
            "ddg_hits": self.ddg_hits,
            "rate_limit_window_count": rate_limiter.current_count,
        }


stats = ServiceStats()

# ---------------------------------------------------------------------------
# Browser lifecycle (singleton Playwright browser)
# ---------------------------------------------------------------------------

_browser: Browser | None = None
_playwright_instance = None


async def get_browser() -> Browser:
    global _browser, _playwright_instance
    if _browser is None or not _browser.is_connected():
        logger.info("Playwright: Chromium ब्राउज़र शुरू हो रहा है… / Starting Chromium browser…")
        _playwright_instance = await async_playwright().start()
        _browser = await _playwright_instance.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-zygote",
                "--single-process",
                "--disable-extensions",
            ],
        )
        logger.info("Playwright: ब्राउज़र तैयार / Browser ready")
    return _browser


async def close_browser() -> None:
    global _browser, _playwright_instance
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright_instance:
        await _playwright_instance.stop()
        _playwright_instance = None
    logger.info("Playwright: ब्राउज़र बंद / Browser closed")


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TILLU WebSearch सेवा शुरू हो रही है… / Service starting…")
    await get_browser()
    yield
    logger.info("TILLU WebSearch सेवा बंद हो रही है… / Service shutting down…")
    await close_browser()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TILLU WebSearch",
    description="Unified web search + scrape service for TILLU AI",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    lang: str = Field("auto", description="Language: hi | en | auto")
    max_results: int = Field(10, ge=1, le=50, description="Max results to return")
    scrape_content: bool = Field(False, description="Also scrape each result page")

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if v not in ("hi", "en", "auto"):
            raise ValueError("lang must be 'hi', 'en', or 'auto'")
        return v


class ScrapeRequest(BaseModel):
    url: str = Field(..., description="URL to scrape")
    extract_text: bool = Field(True, description="Extract readable text via readability")
    screenshot: bool = Field(False, description="Return base64 screenshot (not implemented in this version)")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        return v


class SearchAndScrapeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    lang: str = Field("auto", description="Language: hi | en | auto")
    max_results: int = Field(10, ge=1, le=50)
    scrape_top: int = Field(3, ge=1, le=10, description="Scrape top N results")

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        if v not in ("hi", "en", "auto"):
            raise ValueError("lang must be 'hi', 'en', or 'auto'")
        return v


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    content: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    lang: str
    total: int
    source: str  # "brave" | "duckduckgo"


class ScrapeResponse(BaseModel):
    url: str
    title: str
    text: str
    links: list[str]
    success: bool
    error: str | None = None


class SearchAndScrapeResult(BaseModel):
    title: str
    url: str
    snippet: str
    content: str | None = None
    scraped: bool = False


class SearchAndScrapeResponse(BaseModel):
    query: str
    lang: str
    results: list[SearchAndScrapeResult]


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

HINDI_UNICODE_RANGE = re.compile(r"[\u0900-\u097F]")


def detect_language(text: str) -> str:
    """
    Detect whether text is Hindi or English.
    Hindi Devanagari characters are a strong signal.
    Falls back to langdetect for ambiguous cases.
    """
    if HINDI_UNICODE_RANGE.search(text):
        return "hi"
    try:
        detected = detect(text)
        return "hi" if detected == "hi" else "en"
    except LangDetectException:
        return "en"


def resolve_lang(lang: str, query: str) -> str:
    if lang == "auto":
        return detect_language(query)
    return lang


def lang_params(lang: str) -> dict[str, str]:
    """Return locale params for search APIs."""
    if lang == "hi":
        return {"hl": "hi", "gl": "in", "lr": "lang_hi"}
    return {"hl": "en", "gl": "us", "lr": "lang_en"}


# ---------------------------------------------------------------------------
# HTTP client (shared, with retries)
# ---------------------------------------------------------------------------

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                )
            },
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _http_client


# ---------------------------------------------------------------------------
# Brave Search
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def search_brave(query: str, lang: str, max_results: int) -> list[SearchResult]:
    """Search using Brave Search API."""
    if not BRAVE_API_KEY:
        raise ValueError("BRAVE_API_KEY not configured / BRAVE_API_KEY सेट नहीं है")

    lp = lang_params(lang)
    params: dict[str, Any] = {
        "q": query,
        "count": min(max_results, 20),
        "search_lang": "hi" if lang == "hi" else "en",
        "country": lp["gl"].upper(),
        "text_decorations": False,
        "spellcheck": False,
    }

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }

    client = get_http_client()
    logger.debug("Brave Search: '%s' (lang=%s)", query, lang)
    response = await client.get(BRAVE_SEARCH_URL, params=params, headers=headers)
    response.raise_for_status()

    data = response.json()
    web_results = data.get("web", {}).get("results", [])

    results: list[SearchResult] = []
    for item in web_results[:max_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                content=None,
            )
        )

    logger.info(
        "Brave Search: '%s' → %d परिणाम / results (lang=%s)", query, len(results), lang
    )
    return results


# ---------------------------------------------------------------------------
# DuckDuckGo HTML fallback
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def search_duckduckgo(query: str, lang: str, max_results: int) -> list[SearchResult]:
    """Scrape DuckDuckGo HTML search results as fallback."""
    lp = lang_params(lang)
    params = {
        "q": query,
        "kl": "in-hi" if lang == "hi" else "us-en",
        "kp": "-2",   # safe search off
        "k1": "-1",   # ads off
    }

    client = get_http_client()
    logger.debug("DuckDuckGo fallback: '%s' (lang=%s)", query, lang)

    response = await client.post(
        DDG_HTML_URL,
        data=params,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Language": "hi-IN,hi;q=0.9,en;q=0.8" if lang == "hi" else "en-US,en;q=0.9",
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    results: list[SearchResult] = []

    for result_div in soup.select(".result__body")[:max_results]:
        title_tag = result_div.select_one(".result__title a")
        snippet_tag = result_div.select_one(".result__snippet")

        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        raw_url = title_tag.get("href", "")

        # DDG wraps URLs — extract the real one
        url = _extract_ddg_url(raw_url)
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

        if url:
            results.append(SearchResult(title=title, url=url, snippet=snippet, content=None))

    logger.info(
        "DuckDuckGo: '%s' → %d परिणाम / results (lang=%s)", query, len(results), lang
    )
    return results


def _extract_ddg_url(raw: str) -> str:
    """Extract real URL from DuckDuckGo redirect wrapper."""
    if not raw:
        return ""
    # DDG HTML uses //duckduckgo.com/l/?uddg=<encoded_url>
    if "uddg=" in raw:
        match = re.search(r"uddg=([^&]+)", raw)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))
    if raw.startswith("http"):
        return raw
    return ""


# ---------------------------------------------------------------------------
# Unified search (Brave → DDG fallback)
# ---------------------------------------------------------------------------

async def do_search(query: str, lang: str, max_results: int) -> tuple[list[SearchResult], str]:
    """
    Try Brave first; fall back to DuckDuckGo.
    Returns (results, source_name).
    """
    if BRAVE_API_KEY:
        try:
            results = await search_brave(query, lang, max_results)
            stats.brave_hits += 1
            return results, "brave"
        except Exception as exc:
            logger.warning(
                "Brave Search विफल / failed: %s — DuckDuckGo पर जा रहे हैं / falling back", exc
            )

    results = await search_duckduckgo(query, lang, max_results)
    stats.ddg_hits += 1
    return results, "duckduckgo"


# ---------------------------------------------------------------------------
# Playwright scraper
# ---------------------------------------------------------------------------

async def scrape_url(url: str, extract_text: bool = True) -> ScrapeResponse:
    """
    Use Playwright headless Chromium to load a page and extract content.
    Uses readability-lxml for main-content extraction.
    """
    browser = await get_browser()
    context: BrowserContext | None = None

    try:
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "hi-IN,hi;q=0.9,en-US,en;q=0.8",
            },
        )
        page = await context.new_page()

        # Block heavy resources to speed up scraping
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font", "stylesheet")
            else route.continue_(),
        )

        logger.debug("Playwright: '%s' लोड हो रहा है / loading", url)
        await page.goto(url, wait_until="domcontentloaded", timeout=20_000)

        # Wait a moment for JS-rendered content
        await page.wait_for_timeout(1500)

        title = await page.title()
        html_content = await page.content()

        # Extract all links
        links_raw = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.href).filter(h => h.startsWith('http'))",
        )
        links = list(dict.fromkeys(links_raw))[:50]  # deduplicate, cap at 50

        text = ""
        if extract_text:
            text = _extract_readable_text(html_content, url)

        logger.info("Playwright: '%s' → %d chars, %d links", url, len(text), len(links))
        return ScrapeResponse(url=url, title=title, text=text, links=links, success=True)

    except Exception as exc:
        logger.error("Playwright scrape विफल / failed for '%s': %s", url, exc)
        return ScrapeResponse(
            url=url,
            title="",
            text="",
            links=[],
            success=False,
            error=f"Scrape failed: {exc}",
        )
    finally:
        if context:
            await context.close()


def _extract_readable_text(html: str, url: str) -> str:
    """Use readability-lxml to extract main article text."""
    try:
        doc = Document(html)
        summary_html = doc.summary(html_partial=True)
        soup = BeautifulSoup(summary_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    except Exception as exc:
        logger.warning("readability विफल / failed for '%s': %s — raw text fallback", url, exc)
        # Fallback: strip all tags
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)[:10_000]


# ---------------------------------------------------------------------------
# Rate-limit middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health/status probes
    if request.url.path in ("/health", "/status"):
        return await call_next(request)

    allowed = await rate_limiter.check()
    if not allowed:
        stats.errors_total += 1
        logger.warning("Rate limit exceeded / दर सीमा पार हो गई")
        return ORJSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "detail": "अधिकतम 100 अनुरोध प्रति मिनट / Max 100 requests per minute",
            },
        )

    stats.requests_total += 1
    return await call_next(request)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_class=ORJSONResponse)
async def health():
    """Liveness probe."""
    return {"status": "ok", "service": "tillu-websearch"}


@app.get("/status", response_class=ORJSONResponse)
async def service_status():
    """Service statistics."""
    return {
        "service": "tillu-websearch",
        "version": "1.0.0",
        "brave_configured": bool(BRAVE_API_KEY),
        **stats.to_dict(),
    }


@app.post("/search", response_model=SearchResponse, response_class=ORJSONResponse)
async def search(req: SearchRequest):
    """
    Search the web.

    - Uses Brave Search API if BRAVE_API_KEY is set, otherwise DuckDuckGo HTML.
    - Auto-detects Hindi vs English when lang='auto'.
    - Optionally scrapes each result page for full content.
    """
    stats.searches_total += 1
    resolved_lang = resolve_lang(req.lang, req.query)
    logger.info(
        "Search: '%s' (lang=%s→%s, max=%d, scrape=%s)",
        req.query, req.lang, resolved_lang, req.max_results, req.scrape_content,
    )

    try:
        results, source = await do_search(req.query, resolved_lang, req.max_results)
    except Exception as exc:
        stats.errors_total += 1
        logger.error("Search विफल / failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Search failed / खोज विफल: {exc}",
        )

    if req.scrape_content and results:
        scrape_tasks = [scrape_url(r.url) for r in results]
        scraped = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        for result, scrape_data in zip(results, scraped):
            if isinstance(scrape_data, ScrapeResponse) and scrape_data.success:
                result.content = scrape_data.text[:5_000]  # cap content size

    return SearchResponse(
        results=results,
        query=req.query,
        lang=resolved_lang,
        total=len(results),
        source=source,
    )


@app.post("/scrape", response_model=ScrapeResponse, response_class=ORJSONResponse)
async def scrape(req: ScrapeRequest):
    """
    Scrape a single URL using headless Chromium.

    Returns title, clean readable text, and all outbound links.
    """
    stats.scrapes_total += 1
    logger.info("Scrape: '%s' (extract_text=%s)", req.url, req.extract_text)

    result = await scrape_url(req.url, extract_text=req.extract_text)

    if not result.success:
        # Still return 200 with success=False so callers can handle gracefully
        return result

    return result


@app.post("/search-and-scrape", response_model=SearchAndScrapeResponse, response_class=ORJSONResponse)
async def search_and_scrape(req: SearchAndScrapeRequest):
    """
    Search the web, then scrape the top-N results for full content.

    Combines /search + /scrape in a single optimised call.
    """
    stats.searches_total += 1
    resolved_lang = resolve_lang(req.lang, req.query)
    logger.info(
        "Search+Scrape: '%s' (lang=%s→%s, max=%d, scrape_top=%d)",
        req.query, req.lang, resolved_lang, req.max_results, req.scrape_top,
    )

    # Step 1: search
    try:
        search_results, source = await do_search(req.query, resolved_lang, req.max_results)
    except Exception as exc:
        stats.errors_total += 1
        logger.error("Search विफल / failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Search failed / खोज विफल: {exc}",
        )

    # Step 2: scrape top-N concurrently
    to_scrape = search_results[: req.scrape_top]
    rest = search_results[req.scrape_top :]

    scrape_tasks = [scrape_url(r.url) for r in to_scrape]
    scraped_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

    combined: list[SearchAndScrapeResult] = []

    for sr, scrape_data in zip(to_scrape, scraped_results):
        content = None
        scraped = False
        if isinstance(scrape_data, ScrapeResponse) and scrape_data.success:
            content = scrape_data.text[:5_000]
            scraped = True
            stats.scrapes_total += 1
        combined.append(
            SearchAndScrapeResult(
                title=sr.title,
                url=sr.url,
                snippet=sr.snippet,
                content=content,
                scraped=scraped,
            )
        )

    for sr in rest:
        combined.append(
            SearchAndScrapeResult(
                title=sr.title,
                url=sr.url,
                snippet=sr.snippet,
                content=None,
                scraped=False,
            )
        )

    logger.info(
        "Search+Scrape: '%s' → %d results, %d scraped (source=%s)",
        req.query, len(combined), req.scrape_top, source,
    )

    return SearchAndScrapeResponse(
        query=req.query,
        lang=resolved_lang,
        results=combined,
    )


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    stats.errors_total += 1
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error / आंतरिक सर्वर त्रुटि",
            "detail": str(exc),
        },
    )
