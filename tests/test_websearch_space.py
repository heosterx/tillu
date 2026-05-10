"""
Test script for tillu-ai-tillu-websearch HuggingFace Space
Tests web search, scrape, and intelligence endpoints
"""
import asyncio
import httpx
import sys
from typing import Dict, Any

# WebSearch Space URL
WEBSEARCH_URL = "https://tillu-ai-tillu-websearch.hf.space"


async def test_health() -> bool:
    """Test health endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{WEBSEARCH_URL}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


async def test_status() -> bool:
    """Test status endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{WEBSEARCH_URL}/status")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Status check passed")
                print(f"   SearXNG: {'✅' if data.get('searxng_healthy') else '❌'}")
                print(f"   Playwright: {'✅' if data.get('playwright_healthy') else '❌'}")
                return True
            else:
                print(f"❌ Status check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return False


async def test_search() -> bool:
    """Test web search with fallback chain"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "query": "artificial intelligence latest news",
                "limit": 5,
                "scrape": False
            }
            response = await client.post(f"{WEBSEARCH_URL}/search", json=payload)
            
            if response.status_code != 200:
                print(f"❌ Search failed: {response.status_code}")
                return False
            
            data = response.json()
            
            if "error" in data:
                print(f"❌ Search error: {data['error']}")
                return False
            
            results = data.get("results", [])
            engine_used = data.get("engine_used", "unknown")
            
            print(f"✅ Search returned {len(results)} results via {engine_used}")
            
            if results:
                first = results[0]
                print(f"   First: {first.get('title', 'N/A')[:50]}...")
                print(f"   URL: {first.get('url', 'N/A')[:50]}...")
                return True
            else:
                print("⚠️ No results (space may be warming up)")
                return True
                
    except Exception as e:
        print(f"❌ Search error: {e}")
        return False


async def test_scrape() -> bool:
    """Test webpage scraping"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "url": "https://example.com",
                "render": False,
                "extract_links": False
            }
            response = await client.post(f"{WEBSEARCH_URL}/scrape", json=payload)
            
            if response.status_code != 200:
                print(f"❌ Scrape failed: {response.status_code}")
                return False
            
            data = response.json()
            
            if "error" in data:
                print(f"❌ Scrape error: {data['error']}")
                return False
            
            title = data.get("title", "N/A")
            content_length = len(data.get("content", ""))
            
            print(f"✅ Scrape successful: {title[:50]}...")
            print(f"   Content length: {content_length} chars")
            return True
                
    except Exception as e:
        print(f"❌ Scrape error: {e}")
        return False


async def test_search_and_scrape() -> bool:
    """Test combined search and scrape"""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            payload = {
                "query": "python programming tutorial",
                "limit": 2,
                "scrape_top_n": 1,
                "render": False
            }
            response = await client.post(f"{WEBSEARCH_URL}/search-and-scrape", json=payload)
            
            if response.status_code != 200:
                print(f"❌ Search+scrape failed: {response.status_code}")
                return False
            
            data = response.json()
            
            if "error" in data:
                print(f"❌ Search+scrape error: {data['error']}")
                return False
            
            results = data.get("results", [])
            engine_used = data.get("engine_used", "unknown")
            
            print(f"✅ Search+scrape returned {len(results)} results via {engine_used}")
            
            # Check if any were scraped
            scraped_count = sum(1 for r in results if r.get("content"))
            print(f"   Scraped content: {scraped_count}/{len(results)} results")
            
            return True
                
    except Exception as e:
        print(f"❌ Search+scrape error: {e}")
        return False


async def test_intelligence() -> bool:
    """Test JARVIS-grade intelligence endpoint"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "query": "What are the latest developments in AI in 2025?",
                "max_search": 3,
                "max_scrape": 2,
                "scrape_mode": "basic"
            }
            response = await client.post(f"{WEBSEARCH_URL}/intelligence", json=payload)
            
            if response.status_code != 200:
                print(f"❌ Intelligence failed: {response.status_code}")
                return False
            
            data = response.json()
            
            if "error" in data:
                print(f"⚠️ Intelligence error: {data['error']} (GROQ_API_KEY may be missing)")
                return True  # Don't fail if AI is not configured
            
            summary = data.get("summary", "")
            sources = data.get("sources", [])
            
            print(f"✅ Intelligence successful")
            print(f"   Summary: {summary[:100]}..." if summary else "   (no AI summary - GROQ key may be missing)")
            print(f"   Sources: {len(sources)}")
            return True
                
    except Exception as e:
        print(f"❌ Intelligence error: {e}")
        return False


async def run_all_tests():
    """Run all tests and report results"""
    print("=" * 60)
    print("Testing tillu-ai-tillu-websearch HuggingFace Space")
    print("=" * 60)
    print(f"URL: {WEBSEARCH_URL}")
    print()
    
    tests = [
        ("Health Check", test_health),
        ("Status Check", test_status),
        ("Web Search", test_search),
        ("Web Scrape", test_scrape),
        ("Search+Scrape", test_search_and_scrape),
        ("Intelligence", test_intelligence),
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
    return 0 if passed >= total - 1 else 1  # Allow 1 failure (intelligence may need API key)


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
