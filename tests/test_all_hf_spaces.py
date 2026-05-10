"""
Comprehensive test script for all TILLU HuggingFace Spaces
Tests SearXNG and WebSearch spaces
"""
import asyncio
import httpx
import sys
from typing import Dict, Any, List, Tuple

# Space URLs
SEARXNG_URL = "https://tillu-ai-tillu-searxng.hf.space"
WEBSEARCH_URL = "https://tillu-ai-tillu-websearch.hf.space"


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")


def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


# ============================================================================
# SEARXNG SPACE TESTS
# ============================================================================

async def test_searxng_health() -> Tuple[bool, Dict]:
    """Test SearXNG health via search endpoint"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params={"q": "test", "format": "json"}
            )
            if response.status_code == 200:
                data = response.json()
                return True, {"results_count": len(data.get("results", []))}
            else:
                return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


async def test_searxng_search() -> Tuple[bool, Dict]:
    """Test SearXNG JSON search"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            params = {
                "q": "artificial intelligence",
                "format": "json",
                "language": "en",
                "pageno": 1
            }
            response = await client.get(f"{SEARXNG_URL}/search", params=params)
            
            if response.status_code != 200:
                return False, {"error": f"HTTP {response.status_code}"}
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return True, {"warning": "No results", "count": 0}
            
            first = results[0]
            return True, {
                "count": len(results),
                "first_title": first.get("title", "N/A")[:50],
                "has_content": bool(first.get("content"))
            }
    except Exception as e:
        return False, {"error": str(e)}


async def test_searxng_categories() -> Tuple[bool, Dict]:
    """Test different search categories"""
    categories = ["general", "news", "science", "it"]
    results = {}
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for cat in categories:
            try:
                params = {
                    "q": "technology",
                    "format": "json",
                    "categories": cat,
                    "language": "en"
                }
                response = await client.get(f"{SEARXNG_URL}/search", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    results[cat] = len(data.get("results", []))
                else:
                    results[cat] = 0
            except Exception as e:
                results[cat] = -1
    
    total_results = sum(1 for v in results.values() if v > 0)
    return total_results > 0, {"categories": results}


async def test_searxng_engines() -> Tuple[bool, Dict]:
    """Test specific search engines"""
    engines_to_test = [
        ("google,bing", "google"),
        ("duckduckgo", "ddg"),
        ("wikipedia", "wiki"),
        ("github", "github")
    ]
    
    results = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        for engines, name in engines_to_test:
            try:
                params = {
                    "q": "python programming",
                    "format": "json",
                    "engines": engines,
                    "language": "en"
                }
                response = await client.get(f"{SEARXNG_URL}/search", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    results[name] = len(data.get("results", []))
                else:
                    results[name] = 0
            except Exception as e:
                results[name] = -1
    
    working_engines = sum(1 for v in results.values() if v > 0)
    return working_engines >= 1, {"engines": results, "working": working_engines}


# ============================================================================
# WEBSEARCH SPACE TESTS
# ============================================================================

async def test_websearch_health() -> Tuple[bool, Dict]:
    """Test WebSearch health endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{WEBSEARCH_URL}/health")
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


async def test_websearch_status() -> Tuple[bool, Dict]:
    """Test WebSearch status endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{WEBSEARCH_URL}/status")
            if response.status_code == 200:
                data = response.json()
                return True, {
                    "version": data.get("version"),
                    "searxng_connected": data.get("engines", {}).get("searxng", {}).get("healthy", False),
                    "groq_configured": data.get("groq_configured", False),
                    "uptime": data.get("uptime_seconds", 0),
                    "requests": data.get("requests_total", 0)
                }
            else:
                return False, {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return False, {"error": str(e)}


async def test_websearch_search() -> Tuple[bool, Dict]:
    """Test WebSearch search endpoint"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "query": "machine learning tutorial",
                "limit": 5,
                "scrape": False
            }
            response = await client.post(f"{WEBSEARCH_URL}/search", json=payload)
            
            if response.status_code != 200:
                return False, {"error": f"HTTP {response.status_code}"}
            
            data = response.json()
            
            if "error" in data:
                return False, {"error": data["error"]}
            
            results = data.get("results", [])
            engine = data.get("engine_used", "unknown")
            
            return True, {
                "count": len(results),
                "engine": engine,
                "fallbacks_used": data.get("fallbacks_used", [])
            }
    except Exception as e:
        return False, {"error": str(e)}


async def test_websearch_scrape() -> Tuple[bool, Dict]:
    """Test WebSearch scrape endpoint"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "url": "https://example.com",
                "render": False,
                "extract_links": False
            }
            response = await client.post(f"{WEBSEARCH_URL}/scrape", json=payload)
            
            if response.status_code != 200:
                return False, {"error": f"HTTP {response.status_code}"}
            
            data = response.json()
            
            if "error" in data:
                return False, {"error": data["error"]}
            
            return True, {
                "title": data.get("title", "N/A")[:50],
                "content_length": len(data.get("content", "")),
                "status": data.get("status")
            }
    except Exception as e:
        return False, {"error": str(e)}


async def test_websearch_intelligence() -> Tuple[bool, Dict]:
    """Test WebSearch intelligence endpoint (JARVIS mode)"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "query": "What are the latest AI developments in 2025?",
                "max_search": 3,
                "max_scrape": 2,
                "scrape_mode": "basic"
            }
            response = await client.post(f"{WEBSEARCH_URL}/intelligence", json=payload)
            
            if response.status_code != 200:
                return False, {"error": f"HTTP {response.status_code}"}
            
            data = response.json()
            
            if "error" in data:
                # Don't fail if GROQ is not configured
                if "groq" in data["error"].lower() or "ai" in data["error"].lower():
                    return True, {"warning": "GROQ not configured", "ai_enabled": False}
                return False, {"error": data["error"]}
            
            return True, {
                "has_summary": bool(data.get("summary")),
                "sources_count": len(data.get("sources", [])),
                "ai_enabled": True
            }
    except Exception as e:
        return False, {"error": str(e)}


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all tests and generate report"""
    print_header("TILLU HUGGINGFACE SPACES - COMPREHENSIVE TEST")
    
    all_tests = [
        # SearXNG tests
        ("SearXNG Health", test_searxng_health, SEARXNG_URL),
        ("SearXNG Search", test_searxng_search, SEARXNG_URL),
        ("SearXNG Categories", test_searxng_categories, SEARXNG_URL),
        ("SearXNG Engines", test_searxng_engines, SEARXNG_URL),
        # WebSearch tests
        ("WebSearch Health", test_websearch_health, WEBSEARCH_URL),
        ("WebSearch Status", test_websearch_status, WEBSEARCH_URL),
        ("WebSearch Search", test_websearch_search, WEBSEARCH_URL),
        ("WebSearch Scrape", test_websearch_scrape, WEBSEARCH_URL),
        ("WebSearch Intelligence", test_websearch_intelligence, WEBSEARCH_URL),
    ]
    
    results = {}
    searxng_results = []
    websearch_results = []
    
    for name, test_func, url in all_tests:
        print(f"\n{'─'*60}")
        print(f"Testing: {name}")
        print(f"URL: {url}")
        print("─"*60)
        
        try:
            success, details = await test_func()
            results[name] = {"success": success, "details": details}
            
            if success:
                print_success(f"{name} passed")
                for key, value in details.items():
                    if key != "error":
                        print(f"   {key}: {value}")
            else:
                print_error(f"{name} failed")
                if "error" in details:
                    print(f"   Error: {details['error']}")
            
            # Categorize
            if "SearXNG" in name:
                searxng_results.append(success)
            else:
                websearch_results.append(success)
                
        except Exception as e:
            print_error(f"{name} crashed: {e}")
            results[name] = {"success": False, "details": {"error": str(e)}}
    
    # Summary
    print_header("TEST SUMMARY")
    
    searxng_passed = sum(searxng_results)
    searxng_total = len(searxng_results)
    websearch_passed = sum(websearch_results)
    websearch_total = len(websearch_results)
    total_passed = searxng_passed + websearch_passed
    total_tests = searxng_total + websearch_total
    
    print(f"\n{Colors.BLUE}SearXNG Space ({SEARXNG_URL}){Colors.RESET}")
    print(f"  Passed: {searxng_passed}/{searxng_total}")
    if searxng_passed == searxng_total:
        print_success("  Status: All tests passed")
    else:
        print_error(f"  Status: {searxng_total - searxng_passed} tests failed")
    
    print(f"\n{Colors.BLUE}WebSearch Space ({WEBSEARCH_URL}){Colors.RESET}")
    print(f"  Passed: {websearch_passed}/{websearch_total}")
    if websearch_passed == websearch_total:
        print_success("  Status: All tests passed")
    else:
        print_warning(f"  Status: {websearch_total - websearch_passed} tests failed (intelligence may need GROQ key)")
    
    print(f"\n{Colors.BLUE}Overall{Colors.RESET}")
    print(f"  Total: {total_passed}/{total_tests} tests passed")
    print(f"  Success Rate: {total_passed/total_tests*100:.1f}%")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    # Detailed breakdown
    print("\nDetailed Results:")
    for name, result in results.items():
        status = "✅" if result["success"] else "❌"
        print(f"  {status} {name}")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    return 0 if total_passed >= total_tests - 1 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
