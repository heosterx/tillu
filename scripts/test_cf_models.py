"""Test both Cloudflare AI models used by TILLU."""
import asyncio
import httpx
import json
import os

ACCOUNT_ID   = os.environ.get("CF_ACCOUNT_ID", "")
GATEWAY_ID   = os.environ.get("CF_GATEWAY_ID", "default")
TOKEN_GPT    = os.environ.get("CF_TOKEN_GPT", "")
TOKEN_CLAUDE = os.environ.get("CF_TOKEN_CLAUDE", "")
OPENAI_KEY   = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

PROMPT = "Ek Indian ladke ke liye kal ka weather kya hoga Delhi mein? Short mein batao."

async def test_workers_ai():
    """Model 1: @cf/meta/llama-3.1-8b-instruct — FREE, no provider key needed."""
    print("=" * 55)
    print("Model 1: @cf/meta/llama-3.1-8b-instruct (Workers AI)")
    print("Token:   CF_TOKEN_GPT")
    print("Cost:    FREE")
    print("=" * 55)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/meta/llama-3.1-8b-instruct",
            headers={"Authorization": f"Bearer {TOKEN_GPT}", "Content-Type": "application/json"},
            json={
                "messages": [
                    {"role": "system", "content": "Tu TILLU hai — ek Indian personal AI. NCR (Delhi/Noida) ke liye respond kar. Hindi-English mix mein baat kar."},
                    {"role": "user", "content": PROMPT}
                ],
                "max_tokens": 150,
            }
        )
    if r.status_code == 200:
        content = r.json().get("result", {}).get("response", "")
        usage   = r.json().get("result", {}).get("usage", {})
        print(f"Status:  OK ({r.status_code})")
        print(f"Tokens:  {usage}")
        print(f"Response:\n  {content}")
        return True
    else:
        print(f"Status:  FAIL ({r.status_code})")
        print(f"Error:   {r.text[:200]}")
        return False


async def test_cf_openai():
    """Model 2: openai/gpt-5.5-pro via CF gateway — needs OPENAI_API_KEY."""
    print()
    print("=" * 55)
    print("Model 2: openai/gpt-5.5-pro (CF AI Gateway → OpenAI)")
    print("Token:   CF_TOKEN_GPT + OPENAI_API_KEY")
    print("=" * 55)
    if not OPENAI_KEY or OPENAI_KEY.startswith("YOUR_") or OPENAI_KEY.startswith("sk-YOUR"):
        print("Status:  SKIP — OPENAI_API_KEY not set")
        print("To enable: add OPENAI_API_KEY with credits to .env")
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"https://gateway.ai.cloudflare.com/v1/{ACCOUNT_ID}/{GATEWAY_ID}/openai/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "cf-aig-authorization": f"Bearer {TOKEN_GPT}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-5.5-pro",
                "messages": [
                    {"role": "system", "content": "Tu TILLU hai — ek Indian personal AI. NCR ke liye respond kar."},
                    {"role": "user", "content": PROMPT}
                ],
                "max_tokens": 150,
            }
        )
    if r.status_code == 200:
        data    = r.json()
        content = data["choices"][0]["message"]["content"]
        usage   = data.get("usage", {})
        print(f"Status:  OK ({r.status_code})")
        print(f"Tokens:  {usage}")
        print(f"Response:\n  {content}")
        return True
    else:
        print(f"Status:  FAIL ({r.status_code})")
        print(f"Error:   {r.text[:200]}")
        return False


async def test_cf_anthropic():
    """Model 3: anthropic/claude-opus-4.6 via CF gateway — needs ANTHROPIC_API_KEY."""
    print()
    print("=" * 55)
    print("Model 3: anthropic/claude-opus-4.6 (CF AI Gateway → Anthropic)")
    print("Token:   CF_TOKEN_CLAUDE + ANTHROPIC_API_KEY")
    print("=" * 55)
    if not ANTHROPIC_KEY or ANTHROPIC_KEY.startswith("YOUR_") or ANTHROPIC_KEY.startswith("sk-ant-YOUR"):
        print("Status:  SKIP — ANTHROPIC_API_KEY not set")
        print("To enable: add ANTHROPIC_API_KEY to .env")
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"https://gateway.ai.cloudflare.com/v1/{ACCOUNT_ID}/{GATEWAY_ID}/anthropic/v1/messages",
            headers={
                "Authorization": f"Bearer {ANTHROPIC_KEY}",
                "cf-aig-authorization": f"Bearer {TOKEN_CLAUDE}",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-opus-4-5",
                "max_tokens": 150,
                "system": "Tu TILLU hai — ek Indian personal AI. NCR ke liye respond kar.",
                "messages": [{"role": "user", "content": PROMPT}],
            }
        )
    if r.status_code == 200:
        content = r.json().get("content", [{}])[0].get("text", "")
        usage   = r.json().get("usage", {})
        print(f"Status:  OK ({r.status_code})")
        print(f"Tokens:  {usage}")
        print(f"Response:\n  {content}")
        return True
    else:
        print(f"Status:  FAIL ({r.status_code})")
        print(f"Error:   {r.text[:200]}")
        return False


async def main():
    print()
    print("TILLU — Cloudflare AI Model Tests")
    print(f"Account: {ACCOUNT_ID}")
    print(f"Gateway: {GATEWAY_ID}")
    print(f"Prompt:  {PROMPT}")
    print()

    r1 = await test_workers_ai()
    r2 = await test_cf_openai()
    r3 = await test_cf_anthropic()

    print()
    print("=" * 55)
    print("SUMMARY")
    print("=" * 55)
    print(f"  Workers AI (free llama):  {'OK' if r1 else 'FAIL'}")
    print(f"  CF Gateway → GPT-5.5-pro: {'OK' if r2 else ('SKIP (no key)' if r2 is None else 'FAIL')}")
    print(f"  CF Gateway → Claude:      {'OK' if r3 else ('SKIP (no key)' if r3 is None else 'FAIL')}")
    print()
    if r1:
        print("Workers AI is live and ready — TILLU will use it as CF fallback.")
    if r2 is None:
        print("Add OPENAI_API_KEY with credits to unlock gpt-5.5-pro.")
    if r3 is None:
        print("Add ANTHROPIC_API_KEY to unlock claude-opus-4.6.")


asyncio.run(main())
