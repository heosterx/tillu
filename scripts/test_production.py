"""
TILLU Production Health Check
Tests all live services and reports status.
"""
import httpx
import json
import time

ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwa216a3l6dm15c3Z6bWV2aHJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNDQ4NTMsImV4cCI6MjA5MzcyMDg1M30"
    ".DkEJLAETuU_Df3MPwJXGKr1qYIaIP0KJRjsEA1e7awA"
)

TESTS = [
    {
        "name": "Supabase REST API",
        "url": "https://dpkmzkyzvmysvzmevhrm.supabase.co/rest/v1/user_profile?limit=1",
        "headers": {"apikey": ANON_KEY, "Authorization": "Bearer " + ANON_KEY},
        "expect": [200, 406],   # 406 = no rows but API is alive
    },
    {
        "name": "HF Space — tillu-ai (NLP)",
        "url": "https://tillu-ai-tillu-ai.hf.space/",
        "expect": 200,
    },
    {
        "name": "HF Space — tillu-websearch",
        "url": "https://tillu-ai-tillu-websearch.hf.space/health",
        "expect": 200,
    },
    {
        "name": "HF Space — tillu-engine (n8n) healthz",
        "url": "https://tillu-ai-tillu-engine.hf.space/healthz",
        "expect": 200,
    },
    {
        "name": "HF Space — tillu-engine (n8n) root",
        "url": "https://tillu-ai-tillu-engine.hf.space/",
        "expect": [200, 401],   # 401 = running but auth required (good)
    },
]

print("=" * 55)
print("TILLU Production Health Check")
print("=" * 55)

all_ok = True
for test in TESTS:
    name = test["name"]
    url  = test["url"]
    expected = test["expect"]
    if isinstance(expected, int):
        expected = [expected]

    try:
        t0 = time.time()
        r = httpx.get(url, headers=test.get("headers", {}), timeout=20, follow_redirects=True)
        ms = int((time.time() - t0) * 1000)
        ok = r.status_code in expected
        icon = "OK  " if ok else "FAIL"
        print(f"  [{icon}] {name}")
        print(f"         {r.status_code} in {ms}ms — {url}")
        if not ok:
            all_ok = False
            print(f"         Expected {expected}, got {r.status_code}")
            print(f"         Body: {r.text[:120]}")
    except httpx.TimeoutException:
        print(f"  [FAIL] {name}")
        print(f"         TIMEOUT after 20s — {url}")
        all_ok = False
    except Exception as e:
        print(f"  [FAIL] {name}")
        print(f"         ERROR: {e}")
        all_ok = False
    print()

print("=" * 55)
if all_ok:
    print("All services UP")
else:
    print("Some services need attention — see above")
print("=" * 55)
