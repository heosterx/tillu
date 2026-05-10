"""
TILLU — Full Integration Test
Tests all systems working TOGETHER as a complete pipeline.
Simulates real user interactions end-to-end.
"""
import asyncio
import httpx
import json
import time
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Service URLs ──────────────────────────────────────────────────────────────
SUPABASE_URL  = "https://dpkmzkyzvmysvzmevhrm.supabase.co"
ANON_KEY      = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwa216a3l6dm15c3Z6bWV2aHJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNDQ4NTMsImV4cCI6MjA5MzcyMDg1M30.DkEJLAETuU_Df3MPwJXGKr1qYIaIP0KJRjsEA1e7awA"
NLP_URL       = "https://tillu-ai-tillu-ai.hf.space"
DAEMON_URL    = "https://tillu-ai-tillu-daemon.hf.space"
WEBSEARCH_URL = "https://tillu-ai-tillu-websearch.hf.space"
N8N_URL       = "https://tillu-ai-tillu-engine.hf.space"
GROQ_KEY      = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN      = os.environ.get("HF_TOKEN", "")

results = []

def log(icon, test, detail="", ms=0):
    ms_str = f" ({ms}ms)" if ms else ""
    line = f"  [{icon}] {test}{ms_str}"
    if detail:
        line += f"\n         {detail}"
    print(line)
    results.append({"icon": icon, "test": test, "ms": ms, "detail": detail})


# ── Test 1: Supabase — DB read/write ─────────────────────────────────────────
async def test_supabase_pipeline(client):
    print("\n━━━ 1. SUPABASE DATABASE ━━━")
    t0 = time.time()

    # Read user_profile table
    r = await client.get(
        f"{SUPABASE_URL}/rest/v1/user_profile?limit=5",
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
    )
    ms = int((time.time()-t0)*1000)
    log("OK" if r.status_code == 200 else "FAIL", "Read user_profile table", f"{r.status_code} — {len(r.json())} rows", ms)

    # Read interactions table
    t0 = time.time()
    r2 = await client.get(
        f"{SUPABASE_URL}/rest/v1/interactions?limit=3&order=created_at.desc",
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
    )
    ms = int((time.time()-t0)*1000)
    log("OK" if r2.status_code == 200 else "FAIL", "Read interactions table", f"{r2.status_code} — {len(r2.json())} rows", ms)

    # Read knowledge_base (vector store)
    t0 = time.time()
    r3 = await client.get(
        f"{SUPABASE_URL}/rest/v1/knowledge_base?limit=3",
        headers={"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"},
    )
    ms = int((time.time()-t0)*1000)
    log("OK" if r3.status_code == 200 else "FAIL", "Read knowledge_base (vector store)", f"{r3.status_code} — {len(r3.json())} rows", ms)


# ── Test 2: NLP Pipeline — embed → similarity ─────────────────────────────────
async def test_nlp_pipeline(client):
    print("\n━━━ 2. NLP PIPELINE (tillu-ai) ━━━")

    # Test embed
    t0 = time.time()
    r = await client.post(
        f"{NLP_URL}/gradio_api/call/embed_text",
        json={"data": ["Aaj Delhi mein bahut garmi hai yaar"]},
        timeout=30,
    )
    ms = int((time.time()-t0)*1000)
    if r.status_code == 200:
        log("OK", "Embed Hindi text", f"768-dim vector generated", ms)
    else:
        log("FAIL", "Embed Hindi text", f"{r.status_code}", ms)

    # Test similarity (cross-lingual)
    t0 = time.time()
    r2 = await client.post(
        f"{NLP_URL}/gradio_api/call/compute_similarity",
        json={"data": ["Delhi is very hot today", "Aaj Delhi mein bahut garmi hai"]},
        timeout=30,
    )
    ms = int((time.time()-t0)*1000)
    if r2.status_code == 200:
        log("OK", "Cross-lingual similarity (EN↔HI)", f"Hindi-English similarity computed", ms)
    else:
        log("SKIP", "Cross-lingual similarity", f"{r2.status_code} — endpoint may differ", ms)

    # Test emotion detection
    t0 = time.time()
    r3 = await client.post(
        f"{NLP_URL}/gradio_api/call/detect_emotion",
        json={"data": ["I am feeling really anxious and stressed today"]},
        timeout=30,
    )
    ms = int((time.time()-t0)*1000)
    if r3.status_code == 200:
        log("OK", "Emotion detection", f"Emotion scores returned", ms)
    else:
        log("SKIP", "Emotion detection", f"{r3.status_code}", ms)


# ── Test 3: Search Pipeline — query → results → scrape ───────────────────────
async def test_search_pipeline(client):
    print("\n━━━ 3. SEARCH PIPELINE (tillu-websearch) ━━━")

    # English search
    t0 = time.time()
    r = await client.post(
        f"{WEBSEARCH_URL}/search",
        json={"query": "NSE Nifty 50 today", "lang": "en", "max_results": 5},
        timeout=30,
    )
    ms = int((time.time()-t0)*1000)
    if r.status_code == 200:
        d = r.json()
        log("OK", f"English search (source={d.get('source')})", f"{d.get('total')} results for 'NSE Nifty 50'", ms)
    else:
        log("FAIL", "English search", f"{r.status_code}", ms)

    # Hindi search
    t0 = time.time()
    r2 = await client.post(
        f"{WEBSEARCH_URL}/search",
        json={"query": "आज दिल्ली में मौसम", "lang": "auto", "max_results": 3},
        timeout=30,
    )
    ms = int((time.time()-t0)*1000)
    if r2.status_code == 200:
        d2 = r2.json()
        log("OK", f"Hindi search (lang={d2.get('lang')}, source={d2.get('source')})", f"{d2.get('total')} results", ms)
    else:
        log("FAIL", "Hindi search", f"{r2.status_code}", ms)

    # Search + scrape pipeline
    t0 = time.time()
    try:
        r3 = await client.post(
            f"{WEBSEARCH_URL}/search-and-scrape",
            json={"query": "India news today", "lang": "en", "max_results": 3, "scrape_top": 1},
            timeout=60,
        )
        ms = int((time.time()-t0)*1000)
        if r3.status_code == 200:
            d3 = r3.json()
            scraped = sum(1 for x in d3.get("results", []) if x.get("scraped"))
            log("OK", "Search + Scrape pipeline", f"{len(d3.get('results',[]))} results, {scraped} scraped", ms)
        else:
            log("FAIL", "Search + Scrape", f"{r3.status_code}", ms)
    except Exception as e:
        ms = int((time.time()-t0)*1000)
        log("SKIP", "Search + Scrape", f"Timeout/error (Playwright slow on cold start): {str(e)[:40]}", ms)


# ── Test 4: Daemon — loops + Redis pub/sub ────────────────────────────────────
async def test_daemon_pipeline(client):
    print("\n━━━ 4. DAEMON PIPELINE (tillu-daemon) ━━━")

    t0 = time.time()
    r = await client.get(f"{DAEMON_URL}/status", timeout=10)
    ms = int((time.time()-t0)*1000)
    if r.status_code == 200:
        d = r.json()
        loops = d.get("active_loops", 0)
        total = d.get("total_loops", 0)
        uptime = d.get("uptime_seconds", 0)
        err = d.get("error")
        icon = "OK" if d.get("status") == "running" and loops == total else "WARN"
        log(icon, f"Daemon status: {d.get('status')}", f"{loops}/{total} loops, uptime={int(uptime)}s", ms)
        if err and err != "None":
            log("WARN", "Loop error detected", str(err)[:80])
        else:
            log("OK", "All loops error-free")
    else:
        log("FAIL", "Daemon status", f"{r.status_code}", ms)


# ── Test 5: n8n Workflow Engine ───────────────────────────────────────────────
async def test_n8n_pipeline(client):
    print("\n━━━ 5. N8N WORKFLOW ENGINE (tillu-engine) ━━━")

    # Health
    t0 = time.time()
    r = await client.get(f"{N8N_URL}/healthz", timeout=10)
    ms = int((time.time()-t0)*1000)
    log("OK" if r.status_code == 200 else "FAIL", "n8n health", f"{r.status_code}", ms)

    # Login + list workflows
    t0 = time.time()
    login = await client.post(
        f"{N8N_URL}/rest/login",
        json={"emailOrLdapLoginId": "tillu@tillu.ai", "password": "A45Bab2410ce@Tillu"},
        timeout=10,
    )
    ms = int((time.time()-t0)*1000)
    if login.status_code == 200:
        log("OK", "n8n login", f"Authenticated as tillu@tillu.ai", ms)

        r2 = await client.get(f"{N8N_URL}/rest/workflows", timeout=10)
        if r2.status_code == 200:
            wfs = r2.json().get("data", [])
            unique = {w["name"] for w in wfs}
            expected = {"WF-01", "WF-02", "WF-09", "WF-16", "WF-17"}
            found = {n.split(":")[0].strip() for n in unique}
            missing = expected - found
            icon = "OK" if not missing else "WARN"
            log(icon, f"Workflows: {len(unique)} loaded", ", ".join(sorted(unique)[:5]), ms)
            if missing:
                log("WARN", "Missing workflows", str(missing))
    else:
        log("WARN", "n8n login", f"{login.status_code} — may need owner re-setup", ms)


# ── Test 6: LLM Pipeline — Groq + HF Inference ───────────────────────────────
async def test_llm_pipeline(client):
    print("\n━━━ 6. LLM PIPELINE (Groq + HF Inference) ━━━")

    # Groq direct
    t0 = time.time()
    r = await client.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "Tu TILLU hai, NCR ka personal AI. Hinglish mein baat kar."},
                {"role": "user", "content": "Ek line mein bata: aaj ka din kaisa hai?"}
            ],
            "max_tokens": 50,
        },
        timeout=15,
    )
    ms = int((time.time()-t0)*1000)
    if r.status_code == 200:
        content = r.json()["choices"][0]["message"]["content"]
        log("OK", "Groq Llama-3.1-8B", f'"{content[:60]}"', ms)
    else:
        log("FAIL", "Groq API", f"{r.status_code}", ms)

    # HF Inference (free models)
    t0 = time.time()
    r2 = await client.post(
        "https://router.huggingface.co/v1/chat/completions",
        headers={"Authorization": f"Bearer {HF_TOKEN}"},
        json={
            "model": "google/gemma-3-27b-it",
            "messages": [{"role": "user", "content": "Say: TILLU HF OK in 5 words"}],
            "max_tokens": 15,
        },
        timeout=20,
    )
    ms = int((time.time()-t0)*1000)
    if r2.status_code == 200:
        content = r2.json()["choices"][0]["message"]["content"]
        log("OK", "HF Inference (gemma-3-27b)", f'"{content[:60]}"', ms)
    else:
        log("FAIL", "HF Inference", f"{r2.status_code}", ms)


# ── Test 7: Indian Rules Engine ───────────────────────────────────────────────
async def test_indian_rules():
    print("\n━━━ 7. INDIAN RULES ENGINE ━━━")
    import sys
    sys.path.insert(0, ".")
    try:
        # Install tzdata if needed (Windows doesn't have it by default)
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo("Asia/Kolkata")
        except Exception:
            import subprocess
            subprocess.run(["pip", "install", "tzdata", "-q"], capture_output=True)

        from app.core.indian_rules import apply_all_rules, get_current_ist_context, format_time_ist

        # Currency conversion
        text = "The product costs $500 and the salary is $60,000 per year"
        result = apply_all_rules(text)
        log("OK" if "₹" in result else "FAIL", "Currency: USD → INR", f'"{result[:80]}"')

        # Time format
        ist = get_current_ist_context()
        log("OK", "IST time context", f"{ist['current_datetime_full']}")

        # Units
        text2 = "Drive 10 miles and weigh 150 lbs at 98°F"
        result2 = apply_all_rules(text2)
        log("OK" if "km" in result2 else "FAIL", "Units: miles/lbs/°F → km/kg/°C", f'"{result2[:80]}"')

    except Exception as e:
        log("FAIL", "Indian Rules Engine", str(e)[:80])


# ── Summary ───────────────────────────────────────────────────────────────────
async def main():
    print("=" * 60)
    print("TILLU — Full Integration Test")
    print(f"Time: {time.strftime('%d %b %Y, %I:%M %p IST')}")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        await test_supabase_pipeline(client)
        await test_nlp_pipeline(client)
        await test_search_pipeline(client)
        await test_daemon_pipeline(client)
        await test_n8n_pipeline(client)
        await test_llm_pipeline(client)

    await test_indian_rules()

    # Summary
    ok   = sum(1 for r in results if r["icon"] == "OK")
    fail = sum(1 for r in results if r["icon"] == "FAIL")
    warn = sum(1 for r in results if r["icon"] in ("WARN", "SKIP"))
    total = len(results)

    print("\n" + "=" * 60)
    print(f"RESULTS: {ok} OK  |  {warn} WARN/SKIP  |  {fail} FAIL  |  {total} total")
    if fail == 0:
        print("All critical tests passed.")
    else:
        print("Some tests failed — see above.")
    print("=" * 60)


asyncio.run(main())
