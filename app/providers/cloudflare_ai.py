"""
Cloudflare AI Gateway Provider
================================
Uses Cloudflare Workers AI REST API via the AI Gateway.

Supports:
  - anthropic/claude-opus-4.6  (and other Claude models)
  - @cf/meta/llama-3.1-8b-instruct  (free CF Workers AI models)
  - Any model available via CF AI Gateway

Environment variables required:
  CF_API_TOKEN    — Cloudflare API token (cfut_...)
  CF_ACCOUNT_ID   — Cloudflare Account ID (32-char hex from dashboard)
  CF_GATEWAY_ID   — AI Gateway ID (default: "default")

Docs: https://developers.cloudflare.com/ai-gateway/
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.utils.logging import get_logger

logger = get_logger("cloudflare_ai")

CF_API_TOKEN  = os.environ.get("CF_API_TOKEN", "")
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_GATEWAY_ID = os.environ.get("CF_GATEWAY_ID", "default")

# ── Endpoint templates ────────────────────────────────────────────────────────

def _gateway_url(model: str) -> str:
    """
    AI Gateway URL for external models (Anthropic, OpenAI, etc.)
    https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/{provider}/{model}
    """
    # Map model prefix to provider slug
    if model.startswith("anthropic/"):
        provider = "anthropic"
        model_id = model.replace("anthropic/", "")
        return (
            f"https://gateway.ai.cloudflare.com/v1"
            f"/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/anthropic/v1/messages"
        )
    if model.startswith("openai/") or model.startswith("gpt-"):
        return (
            f"https://gateway.ai.cloudflare.com/v1"
            f"/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/openai/chat/completions"
        )
    # Default: Workers AI (CF native models like @cf/meta/llama-3.1-8b-instruct)
    return (
        f"https://gateway.ai.cloudflare.com/v1"
        f"/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/workers-ai/{model}"
    )


def _workers_ai_url(model: str) -> str:
    """Direct Workers AI URL (no gateway)."""
    return (
        f"https://api.cloudflare.com/client/v4/accounts"
        f"/{CF_ACCOUNT_ID}/ai/run/{model}"
    )


# ── Main async function ───────────────────────────────────────────────────────

async def run(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
    use_gateway: bool = True,
) -> dict[str, Any]:
    """
    Run a model via Cloudflare AI Gateway or Workers AI.

    Args:
        model:       Model ID e.g. "anthropic/claude-opus-4.6"
                     or "@cf/meta/llama-3.1-8b-instruct"
        messages:    OpenAI-style message list
        max_tokens:  Max tokens to generate
        temperature: Sampling temperature
        use_gateway: Use AI Gateway (True) or direct Workers AI (False)

    Returns:
        dict with 'content' (str) and 'model', 'usage' keys
    """
    if not CF_API_TOKEN or not CF_ACCOUNT_ID:
        raise ValueError(
            "CF_API_TOKEN and CF_ACCOUNT_ID must be set. "
            "Get Account ID from dash.cloudflare.com"
        )

    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # ── Anthropic models via gateway ─────────────────────────────────────────
    if model.startswith("anthropic/"):
        model_id = model.replace("anthropic/", "")
        url = (
            f"https://gateway.ai.cloudflare.com/v1"
            f"/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/anthropic/v1/messages"
        )
        payload = {
            "model": model_id,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data.get("content", [{}])[0].get("text", "")
        return {
            "content": content,
            "model": model,
            "usage": data.get("usage", {}),
            "provider": "cloudflare_gateway_anthropic",
        }

    # ── Workers AI native models ──────────────────────────────────────────────
    url = _workers_ai_url(model) if not use_gateway else (
        f"https://gateway.ai.cloudflare.com/v1"
        f"/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}/workers-ai/{model}"
    )
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    # Workers AI wraps response in {"result": {"response": "..."}}
    result = data.get("result", data)
    content = result.get("response", result.get("content", ""))

    return {
        "content": content,
        "model": model,
        "usage": result.get("usage", {}),
        "provider": "cloudflare_workers_ai",
    }


# ── LangChain-compatible wrapper ──────────────────────────────────────────────

class CloudflareAI:
    """
    Minimal LangChain-compatible wrapper for Cloudflare AI.
    Drop-in replacement for ChatGroq / ChatAnthropic in chains.
    """

    def __init__(
        self,
        model: str = "@cf/meta/llama-3.1-8b-instruct",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def ainvoke(self, messages: list) -> Any:
        """Invoke model async. Accepts LangChain message objects or dicts."""
        # Normalise LangChain message objects → dicts
        normalised = []
        for m in messages:
            if hasattr(m, "type") and hasattr(m, "content"):
                role = {"human": "user", "ai": "assistant", "system": "system"}.get(
                    m.type, m.type
                )
                normalised.append({"role": role, "content": m.content})
            elif isinstance(m, dict):
                normalised.append(m)

        result = await run(
            model=self.model,
            messages=normalised,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        # Return object with .content attribute (LangChain compatible)
        class _Response:
            def __init__(self, content: str):
                self.content = content
                self.response_metadata = {}

        return _Response(result["content"])
