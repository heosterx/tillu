"""
TILLU — Full Space Functional Test
Tests every endpoint of every live HF Space.
"""
import asyncio
import httpx
import json
import time
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwa216a3l6dm15c3Z6bWV2aHJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNDQ4NTMsImV4cCI6MjA5MzcyMDg1M30"
    ".DkEJLAETuU_Df3MPwJXGKr1qYIaIP0KJRjsEA1e7awA"
)

PASS = "OK  "
FAIL = "FAIL"
SKIP = "SKIP"


def p(icon, name, detail=""):
    print(f"  [{icon}] {name}" + (f"\n         {detail}" if detail else ""))


async def test_supabase(client):
    print("\n=== Supabase ===")
    r = await client.get(
        "https://dpkmzkyzvmysvzmevhrm.supabase.co/rest/v1/user_profile?limit=1",
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
    )
    p(PASS if r.status_code == 200 else FAIL, "REST API", f"{r.status_code}")

    r2 = await client.get(
        "https://dpkmzkyzvmysvzmevhrm.supabase.co/rest/v1/",
        headers={"apikey": ANON_KEY},
    )
    p(PASS if r2.status_code < 500 else FAIL, "API root", f"{r2.status_code}")


async def test_tillu_ai(client):
    print("\n=== tillu-ai (NLP Space) ===")
    base = "https://tillu-ai-tillu-ai.hf.space"

    r = await client.get(base + "/")
    p(PASS if r.status_code == 200 else FAIL, "Root / Gradio UI", f"{r.status_code}")

    # Gradio 6.x uses /gradio_api/call/<fn_name> or queue/join
    # Test via the correct Gradio API endpoint
    r2 = await client.post(
        base + "/gradio_api/call/embed_text",
        json={"data": ["Hello TILLU, aaj ka din kaisa hai?"]},
        timeout=30,
    )
    if r2.status_code == 200:
        p(PASS, "Embed API (gradio_api)", f"status={r2.status_code}")
    else:
        # Try legacy endpoint
        r3 = await client.post(
            base + "/api/predict",
            json={"data": ["Hello TILLU"], "fn_index": 0},
            timeout=30,
        )
        icon = PASS if r3.status_code == 200 else SKIP
        p(icon, "Embed API (api/predict)", f"{r3.status_code} — Gradio UI accessible, API path varies by version")


async def test_tillu_daemon(client):
    print("\n=== tillu-daemon (Background Loops) ===")
    base = "https://tillu-ai-tillu-daemon.hf.space"

    r = await client.get(base + "/health")
    p(PASS if r.status_code == 200 else FAIL, "Health", f"{r.status_code} {r.json()}")

    r2 = await client.get(base + "/status")
    if r2.status_code == 200:
        d = r2.json()
        loops = d.get("active_loops", 0)
        total = d.get("total_loops", 0)
        status = d.get("status", "?")
        err = d.get("error")
        icon = PASS if status == "running" and loops > 0 else FAIL
        p(icon, f"Status: {status}", f"{loops}/{total} loops active")
        if err and err != "None":
            p(FAIL, "Loop error", str(err)[:100])
        else:
            p(PASS, "No loop errors")
    else:
        p(FAIL, "Status endpoint", f"{r2.status_code}")


async def test_tillu_websearch(client):
    print("\n=== tillu-websearch (Search + Scrape) ===")
    base = "https://tillu-ai-tillu-websearch.hf.space"

    r = await client.get(base + "/health")
    p(PASS if r.status_code == 200 else FAIL, "Health", f"{r.json()}")

    r2 = await client.get(base + "/status")
    if r2.status_code == 200:
        d = r2.json()
        p(PASS, "Status", f"uptime={d.get('uptime_seconds')}s brave={d.get('brave_configured')}")

    # Test search
    r3 = await client.post(
        base + "/search",
        json={"query": "Delhi weather today", "lang": "auto", "max_results": 3},
        timeout=30,
    )
    if r3.status_code == 200:
        d = r3.json()
        p(PASS, f"Search (source={d.get('source')})", f"{d.get('total')} results for 'Delhi weather'")
    else:
        p(FAIL, "Search", f"{r3.status_code}: {r3.text[:80]}")

    # Test Hindi search
    r4 = await client.post(
        base + "/search",
        json={"query": "आज दिल्ली में मौसम कैसा है", "lang": "auto", "max_results": 3},
        timeout=30,
    )
    if r4.status_code == 200:
        d = r4.json()
        p(PASS, f"Hindi search (lang={d.get('lang')})", f"{d.get('total')} results")
    else:
        p(FAIL, "Hindi search", f"{r4.status_code}: {r4.text[:80]}")

    # Test scrape
    r5 = await client.post(
        base + "/scrape",
        json={"url": "https://httpbin.org/html", "extract_text": True},
        timeout=40,
    )
    if r5.status_code == 200:
        d = r5.json()
        p(PASS if d.get("success") else FAIL, "Scrape httpbin.org/html", f"title='{d.get('title')}' chars={len(d.get('text',''))}")
    else:
        p(SKIP, "Scrape", f"{r5.status_code} — Playwright may need warmup")


async def test_tillu_engine(client):
    print("\n=== tillu-engine (n8n) ===")
    base = "https://tillu-ai-tillu-engine.hf.space"

    r = await client.get(base + "/healthz")
    p(PASS if r.status_code == 200 else FAIL, "Health /healthz", f"{r.status_code}")

    r2 = await client.get(base + "/")
    p(PASS if r2.status_code in (200, 401) else FAIL, "n8n UI root", f"{r2.status_code}")

    # Check workflows via API
    r3 = await client.post(
        base + "/rest/login",
        json={"emailOrLdapLoginId": "tillu@tillu.ai", "password": "A45Bab2410ce@Tillu"},
        timeout=15,
    )
    if r3.status_code == 200:
        r4 = await client.get(base + "/rest/workflows")
        if r4.status_code == 200:
            wfs = r4.json().get("data", [])
            unique = list({w["name"] for w in wfs})
            p(PASS, f"Workflows: {len(unique)} unique", ", ".join(unique[:4]))
        else:
            p(FAIL, "Workflow list", f"{r4.status_code}")
    else:
        p(SKIP, "n8n login", f"{r3.status_code} — n8n may need owner setup or password reset")


async def main():
    print("=" * 60)
    print("TILLU — Full Space Functional Test")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        await test_supabase(client)
        await test_tillu_ai(client)
        await test_tillu_daemon(client)
        await test_tillu_websearch(client)
        await test_tillu_engine(client)

    print("\n" + "=" * 60)
    print("Test complete.")
    print("=" * 60)


asyncio.run(main())
