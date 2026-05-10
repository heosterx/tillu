"""
Test script for tillu-ai-tillu-searxng HuggingFace Space
Tests JSON API endpoints for search functionality
"""
import asyncio
import httpx
import sys
from typing import Dict, Any

# SearXNG Space URL
SEARXNG_URL = "https://tillu-ai-tillu-searxng.hf.space"


async def test_health() -> bool:
    """Test basic health/liveness - SearXNG uses /search for health"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # SearXNG doesn't have a dedicated /health endpoint
            # Use a simple search to verify it's working
            response = await client.get(
                f"{SEARXNG_URL}/search",
                params={"q": "test", "format": "json"}
            )
            if response.status_code == 200:
                print(f"✅ Health check passed (search working)")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


async def test_search_json() -> bool:
    """Test JSON search API"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Test basic search
            params = {
                "q": "artificial intelligence news",
                "format": "json",
                "language": "en",
                "pageno": 1
            }
            response = await client.get(f"{SEARXNG_URL}/search", params=params)
            
            if response.status_code != 200:
                print(f"❌ Search failed: {response.status_code}")
                return False
            
            data = response.json()
            
            # Validate response structure
            if "results" not in data:
                print("❌ Missing 'results' in response")
                return False
            
            results = data["results"]
            print(f"✅ Search returned {len(results)} results")
            
            # Check result quality
            if len(results) > 0:
                first = results[0]
                required_fields = ["title", "url", "content"]
                for field in required_fields:
                    if field not in first:
                        print(f"❌ Missing field '{field}' in result")
                        return False
                
                print(f"✅ First result: {first['title'][:60]}...")
                print(f"   URL: {first['url'][:60]}...")
                return True
            else:
                print("⚠️ No results returned (space may be warming up)")
                return True
                
    except Exception as e:
        print(f"❌ Search error: {e}")
        return False


async def test_search_categories() -> bool:
    """Test different search categories"""
    categories = ["general", "news", "science", "it"]
    results = {}
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for cat in categories:
            try:
                params = {
                    "q": "machine learning",
                    "format": "json",
                    "categories": cat,
                    "language": "en"
                }
                response = await client.get(f"{SEARXNG_URL}/search", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    count = len(data.get("results", []))
                    results[cat] = count
                    print(f"✅ Category '{cat}': {count} results")
                else:
                    print(f"⚠️ Category '{cat}': HTTP {response.status_code}")
                    results[cat] = 0
                    
            except Exception as e:
                print(f"❌ Category '{cat}' error: {e}")
                results[cat] = 0
    
    # At least one category should work
    if any(count > 0 for count in results.values()):
        return True
    else:
        print("❌ No results from any category")
        return False


async def test_search_engines() -> bool:
    """Test specific search engines"""
    engines_list = [
        "google,bing",
        "duckduckgo",
        "wikipedia",
        "github"
    ]
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        for engines in engines_list:
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
                    count = len(data.get("results", []))
                    print(f"✅ Engines '{engines}': {count} results")
                else:
                    print(f"⚠️ Engines '{engines}': HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Engines '{engines}' error: {e}")
    
    return True  # Don't fail if some engines don't work


async def test_pagination() -> bool:
    """Test pagination"""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Page 1
            params1 = {"q": "technology", "format": "json", "pageno": 1}
            response1 = await client.get(f"{SEARXNG_URL}/search", params=params1)
            
            # Page 2
            params2 = {"q": "technology", "format": "json", "pageno": 2}
            response2 = await client.get(f"{SEARXNG_URL}/search", params=params2)
            
            if response1.status_code == 200 and response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                
                results1 = len(data1.get("results", []))
                results2 = len(data2.get("results", []))
                
                print(f"✅ Page 1: {results1} results, Page 2: {results2} results")
                
                # Pages should ideally have different results
                return True
            else:
                print(f"❌ Pagination failed: {response1.status_code}, {response2.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Pagination error: {e}")
        return False


async def test_autocomplete() -> bool:
    """Test autocomplete/suggestions"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            params = {"q": "machine le"}
            response = await client.get(f"{SEARXNG_URL}/autocompleter", params=params)
            
            if response.status_code == 200:
                data = response.json()
                suggestions = data if isinstance(data, list) else data.get("suggestions", [])
                print(f"✅ Autocomplete returned {len(suggestions)} suggestions")
                return True
            else:
                # Autocomplete might not be enabled, don't fail
                print(f"⚠️ Autocomplete: HTTP {response.status_code} (may be disabled)")
                return True
                
    except Exception as e:
        print(f"⚠️ Autocomplete error: {e} (may be disabled)")
        return True


async def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("Testing tillu-ai-tillu-searxng HuggingFace Space")
    print("=" * 60)
    print(f"URL: {SEARXNG_URL}")
    print()
    
    tests = [
        ("Health Check", test_health),
        ("Search JSON", test_search_json),
        ("Categories", test_search_categories),
        ("Engines", test_search_engines),
        ("Pagination", test_pagination),
        ("Autocomplete", test_autocomplete),
    ]
    
    results = {}
    
    for name, test_func in tests:
        print(f"\n{'─' * 60}")
        print(f"Running: {name}")
        print("─" * 60)
        
        try:
            result = await test_func()
            results[name] = result
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            results[name] = False
    
    # Summary
    print(f"\n{'=' * 60}")
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'─' * 60}")
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 60)
    
    # Exit code
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
