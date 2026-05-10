"""Test the universal LLM router across all providers."""
import asyncio
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Load env BEFORE any app imports
from dotenv import load_dotenv
load_dotenv()

# Import router directly — bypass app stack (avoids redis/supabase deps)
sys.path.insert(0, ".")

# Patch the logger to avoid importing app.utils
import logging
logging.basicConfig(level=logging.WARNING)

# Monkey-patch get_logger so llm_router doesn't need app.utils
import types
fake_utils = types.ModuleType("app.utils.logging")
fake_utils.get_logger = lambda name: logging.getLogger(name)
sys.modules["app.utils.logging"] = fake_utils
sys.modules["app.utils"] = types.ModuleType("app.utils")
sys.modules["app.utils"].logging = fake_utils


async def main():
    # Import after patching
    import importlib
    import app.providers.hf_inference as hf_mod
    import app.providers.llm_router as router_mod
    invoke   = router_mod.invoke
    providers = router_mod.providers
    select   = router_mod.select

    p = providers()
    active = [k for k, v in p.items() if v]
    print("=" * 55)
    print("TILLU Universal LLM Router Test")
    print("=" * 55)
    print("Available providers:", active)
    print()

    tests = [
        ("quick_chat",    "en", "Say: TILLU OK in 3 words"),
        ("quality_chat",  "hi", "Ek line mein bata: aaj ka din kaisa hai?"),
        ("deep_reasoning","en", "What is 2+2? One word answer only."),
        ("coding",        "en", "Python one-liner: print hello world"),
        ("analysis",      "hi", "Delhi mein garmi kyun hoti hai? 1 sentence."),
    ]

    ok = 0
    for task, lang, prompt in tests:
        sel = select(task, lang)
        provider = sel["provider"]
        model    = sel["model"]
        print("Task=" + task + " lang=" + lang + " -> " + provider + "/" + model[:40])
        try:
            r = await invoke(
                messages=[{"role": "user", "content": prompt}],
                task=task, lang=lang, max_tokens=40
            )
            print("  OK (" + str(r["latency_ms"]) + "ms): " + r["content"][:70])
            ok += 1
        except Exception as e:
            print("  FAIL: " + str(e)[:70])
        print()

    print("=" * 55)
    print("Results: " + str(ok) + "/" + str(len(tests)) + " passed")
    print("=" * 55)


asyncio.run(main())
