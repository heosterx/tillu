import httpx
from typing import Any, Dict, List
from app.config import settings
from app.tools.registry import BaseTool, ToolMetadata, ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("search_tools")

WEBSEARCH_BASE = getattr(settings, "websearch_url", None) or getattr(settings, "searxng_url", "http://localhost:8080")

class WebSearchTool(BaseTool):
    metadata = ToolMetadata(
        name="tool_web_search",
        description="Search the web via TILLU WebSearch (SearXNG -> DDG -> Google fallback chain).",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "lang": {"type": "string", "description": "Language: hi | en | auto", "default": "auto"},
            "num_results": {"type": "integer", "description": "Number of results", "default": 10},
            "categories": {"type": "string", "description": "general | news | science | it", "default": "general"},
        },
        rate_limited=True
    )

    async def execute(self, query: str, lang: str = "auto", num_results: int = 10, categories: str = "general") -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    WEBSEARCH_BASE.rstrip("/") + "/search",
                    json={"query": query, "lang": lang, "max_results": num_results, "categories": categories},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "query": query,
                        "source": data.get("source", "unknown"),
                        "results": [
                            {
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "content": r.get("snippet", r.get("content", "")),
                                "engine": r.get("engine", "unknown"),
                            }
                            for r in data.get("results", [])[:num_results]
                        ],
                        "result_count": data.get("total", 0),
                    }
                return {"success": False, "error": f"Search failed: {resp.status_code}"}
        except Exception as e:
            logger.error(f"WebSearch error: {e}")
            return {"success": False, "error": str(e)}


class IntelligenceTool(BaseTool):
    metadata = ToolMetadata(
        name="tool_intelligence",
        description="JARVIS-mode: search + scrape + AI summarise in one shot. Returns summary, key_points, sources.",
        parameters={
            "query": {"type": "string", "description": "Research query"},
            "lang": {"type": "string", "default": "auto"},
            "mode": {"type": "string", "description": "fast | balanced | deep", "default": "balanced"},
        },
        rate_limited=True
    )

    async def execute(self, query: str, lang: str = "auto", mode: str = "balanced") -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    WEBSEARCH_BASE.rstrip("/") + "/intelligence",
                    json={"query": query, "lang": lang, "mode": mode},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"success": True, **data}
                return {"success": False, "error": f"Intelligence failed: {resp.status_code}"}
        except Exception as e:
            logger.error(f"Intelligence error: {e}")
            return {"success": False, "error": str(e)}


class ScrapePageTool(BaseTool):
    metadata = ToolMetadata(
        name="tool_scrape_page",
        description="Scrape a URL with headless Chromium. Returns title, clean text, links.",
        parameters={"url": {"type": "string", "description": "URL to scrape"}},
        rate_limited=True
    )

    async def execute(self, url: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(
                    WEBSEARCH_BASE.rstrip("/") + "/scrape",
                    json={"url": url},
                )
                if resp.status_code == 200:
                    return {"success": True, **resp.json()}
                return {"success": False, "error": f"Scrape failed: {resp.status_code}"}
        except Exception as e:
            logger.error(f"Scrape error: {e}")
            return {"success": False, "error": str(e)}


ToolRegistry.register(WebSearchTool())
ToolRegistry.register(IntelligenceTool())
ToolRegistry.register(ScrapePageTool())
