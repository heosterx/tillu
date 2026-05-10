"""
Find all free HF Inference Provider models for TILLU.
Endpoint: https://router.huggingface.co/v1/chat/completions
"""
import httpx
import asyncio
import time

import os

TOKEN = os.environ.get("HF_TOKEN", "")
if not TOKEN:
    raise SystemExit("Set HF_TOKEN env var before running: $env:HF_TOKEN='hf_...'")
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
ENDPOINT = "https://router.huggingface.co/v1/chat/completions"

# All candidates to test
CANDIDATES = [
    # Qwen (confirmed working)
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/QwQ-32B",
    "Qwen/Qwen3-30B-A3B",
    "Qwen/Qwen3-8B",
    "Qwen/Qwen3-4B",
    "Qwen/Qwen2.5-32B-Instruct",
    # Meta Llama
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Llama-3.1-70B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Llama-3.2-1B-Instruct",
    # Mistral
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "mistralai/Mistral-Nemo-Instruct-2407",
    "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
    # DeepSeek
    "deepseek-ai/DeepSeek-R1",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "deepseek-ai/DeepSeek-V3-0324",
    # Google
    "google/gemma-2-2b-it",
    "google/gemma-2-9b-it",
    "google/gemma-3-27b-it",
    "google/gemma-3-12b-it",
    "google/gemma-3-4b-it",
    # Microsoft
    "microsoft/Phi-3.5-mini-instruct",
    "microsoft/phi-4",
    # Nvidia
    "nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
    # NovaSky
    "NovaSky-AI/Sky-T1-32B-Preview",
    # Cohere
    "CohereForAI/c4ai-command-r-plus-08-2024",
    # HuggingFace
    "HuggingFaceH4/zephyr-7b-beta",
    # Tiiuae
    "tiiuae/Falcon3-10B-Instruct",
    "tiiuae/Falcon3-7B-Instruct",
]

TEST_MSG = "You are TILLU, Indian AI. Reply in Hinglish in 1 sentence: Aaj ka din kaisa hai?"


async def test_model(model: str) -> dict:
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                ENDPOINT,
                headers=HEADERS,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": TEST_MSG}],
                    "max_tokens": 60,
                },
            )
        latency = int((time.time() - t0) * 1000)

        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            return {"model": model, "status": "OK", "latency_ms": latency, "response": content[:80]}
        elif r.status_code == 400:
            err = r.json().get("error", {}).get("message", "")[:60]
            return {"model": model, "status": "NOT_SUPPORTED", "latency_ms": latency, "error": err}
        elif r.status_code == 429:
            return {"model": model, "status": "RATE_LIMITED", "latency_ms": latency}
        elif r.status_code == 503:
            return {"model": model, "status": "LOADING", "latency_ms": latency}
        else:
            return {"model": model, "status": f"FAIL_{r.status_code}", "latency_ms": latency, "error": r.text[:60]}

    except httpx.TimeoutException:
        return {"model": model, "status": "TIMEOUT", "latency_ms": 20000}
    except Exception as e:
        return {"model": model, "status": "ERROR", "latency_ms": 0, "error": str(e)[:50]}


async def main():
    print("HF Inference Providers — Free Model Discovery")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Testing {len(CANDIDATES)} models...")
    print()

    results = await asyncio.gather(*[test_model(m) for m in CANDIDATES])

    working = sorted([r for r in results if r["status"] == "OK"], key=lambda x: x["latency_ms"])
    other   = [r for r in results if r["status"] != "OK"]

    print(f"{'STATUS':<12} {'MODEL':<50} {'MS':>6}")
    print("=" * 72)
    for r in working:
        print(f"OK          {r['model']:<50} {r['latency_ms']:>5}ms")
        print(f"            {r.get('response','')[:65]}")
        print()

    print("\nNot available:")
    for r in sorted(other, key=lambda x: x["status"]):
        print(f"  {r['status']:<15} {r['model']}")

    print()
    print("=" * 72)
    print(f"Working: {len(working)} / {len(CANDIDATES)}")

    if working:
        print("\nAdd to .env:")
        print("# HF free chat models (router.huggingface.co)")
        for r in working[:8]:
            size = "large" if any(x in r["model"] for x in ["70B","72B","32B","8x7B"]) else "fast"
            print(f"# {r['model']} ({r['latency_ms']}ms) [{size}]")


asyncio.run(main())
