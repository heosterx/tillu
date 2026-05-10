"""
Search Tools
"""
import httpx
from typing import Any, Dict, List
from app.config import settings
from app.tools.registry import BaseTool, ToolMetadata, ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("search_tools")


class WebSearchTool(BaseTool):
    """Search via SearXNG internal API"""
    
    metadata = ToolMetadata(
        name="tool_web_search",
        description="Search the web using SearXNG meta-search engine. Aggregates results from Google, Bing, DuckDuckGo, and more.",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "engines": {"type": "array", "description": "Specific engines to use (optional)"},
            "num_results": {"type": "integer", "description": "Number of results to return", "default": 10}
        },
        rate_limited=True
    )
    
    async def execute(self, query: str, engines: List[str] = None, num_results: int = 10) -> Dict[str, Any]:
        """Execute web search via SearXNG"""
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "q": query,
                    "format": "json",
                    "language": "en"
                }
                if engines:
                    params["engines"] = ",".join(engines)
                
                response = await client.get(
                    f"{settings.searxng_url}/search",
                    params=params,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])[:num_results]
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": [
                            {
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "content": r.get("content"),
                                "engine": r.get("engine")
                            }
                            for r in results
                        ],
                        "result_count": len(results)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Search failed with status {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class BraveSearchTool(BaseTool):
    """Search via Brave Search API"""
    
    metadata = ToolMetadata(
        name="tool_brave_search",
        description="Search using Brave Search API with independent index. Good for diverse results.",
        parameters={
            "query": {"type": "string", "description": "Search query"},
            "num_results": {"type": "integer", "description": "Number of results", "default": 10}
        },
        rate_limited=True,
        requires_auth=True
    )
    
    async def execute(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """Execute Brave search"""
        if not settings.brave_api_key:
            return {
                "success": False,
                "error": "Brave API key not configured"
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": settings.brave_api_key
                    },
                    params={
                        "q": query,
                        "count": num_results
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    web_results = data.get("web", {}).get("results", [])
                    
                    return {
                        "success": True,
                        "query": query,
                        "results": [
                            {
                                "title": r.get("title"),
                                "url": r.get("url"),
                                "description": r.get("description"),
                                "age": r.get("age")
                            }
                            for r in web_results
                        ],
                        "result_count": len(web_results)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Brave search failed: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Brave search error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


# Register tools
ToolRegistry.register(WebSearchTool())
ToolRegistry.register(BraveSearchTool())
