"""
Cloudflare AI Gateway Provider
================================
Routes LLM calls through Cloudflare AI Gateway for logging, caching,
rate limiting, and observability.

Auth pattern (two headers required):
  Authorization:        Bearer <PROVIDER_API_KEY>   ← actual OpenAI/Anthropic key
  cf-aig-authorization: Bearer <CF_GATEWAY_TOKEN>   ← CF gateway token (if auth enabled)

Tokens:
  CF_TOKEN_GPT     = cfut_mrPhD8...  → used for OpenAI calls
  CF_TOKEN_CLAUDE  = cfut_imSasSy... → used for Anthropic calls
  CF_ACCOUNT_ID    = 2d9a6684...
  CF_GATEWAY_ID    = default

Models supported:
  openai/gpt-5.5-pro          → needs OPENAI_API_KEY
  anthropic/claude-opus-4.6   → needs ANTHROPIC_API_KEY
  @cf/meta/llama-3.1-8b-instruct → free, CF token only
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.utils.logging import get_logger

logger = get_logger("cloudflare_ai")

# ── Config ────────────────────────────────────────────────────────────────────
CF_ACCOUNT_ID   = os.environ.get("CF_ACCOUNT_ID", "")
CF_GATEWAY_ID   = os.environ.get("CF_GATEWAY_ID", "default")
CF_TOKEN_GPT    = os.environ.get("CF_TOKEN_GPT", "")     # for OpenAI via gateway
CF_TOKEN_CLAUDE = os.environ.get("CF_TOKEN_CLAUDE", "")  # for Anthropic via gateway
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def _gateway_base() -> str:
    return f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}"


def _workers_ai_url(model: str) -> str:
    return f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{model}"


def is_available(model: str) -> bool:
    """Check if a model can actually be called with current credentials."""
    if not CF_ACCOUNT_ID or CF_ACCOUNT_ID.startswith("YOUR_"):
        return False
    provider = _provider_from_model(model)
    if provider == "openai":
        return bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("YOUR_"))
    if provider == "anthropic":
        return bool(ANTHROPIC_API_KEY and not ANTHROPIC_API_KEY.startswith("YOUR_"))
    if provider == "workers-ai":
        return bool(CF_TOKEN_GPT or CF_TOKEN_CLAUDE)  # any CF token works
    return False


def _provider_from_model(model: str) -> str:
    if model.startswith("openai/") or model.startswith("gpt-"):
        return "openai"
    if model.startswith("anthropic/") or model.startswith("claude-"):
        return "anthropic"
    return "workers-ai"


# ── Main run function ─────────────────────────────────────────────────────────

async def run(
    model: str,
    messages: list[dict[str, str]] | None = None,
    input: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """
    Run a model via Cloudflare AI Gateway.

    For OpenAI/Anthropic models, the gateway proxies the call and adds
    CF observability. Provider API keys are still required.

    For Workers AI models (@cf/...), only the CF token is needed — free tier.
    """
    if not CF_ACCOUNT_ID or CF_ACCOUNT_ID.startswith("YOUR_"):
        raise ValueError("CF_ACCOUNT_ID not set. Get it from dash.cloudflare.com")

    # Normalise input → messages
    if input and not messages:
        messages = [{"role": "user", "content": input}]
    if not messages:
        raise ValueError("Provide either messages or input")

    provider = _provider_from_model(model)

    # ── OpenAI via CF gateway ─────────────────────────────────────────────────
    if provider == "openai":
        if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("YOUR_"):
            raise ValueError("OPENAI_API_KEY required for openai/* models via CF gateway")

        model_id = model.replace("openai/", "")
        url = f"{_gateway_base()}/openai/chat/completions"

        headers: dict[str, str] = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        # Add CF gateway auth token if configured
        if CF_TOKEN_GPT:
            headers["cf-aig-authorization"] = f"Bearer {CF_TOKEN_GPT}"

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        logger.info("CF Gateway → OpenAI: %s", model_id)
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"]
        return {
            "content": content,
            "model": model,
            "provider": "cf_gateway_openai",
            "usage": data.get("usage", {}),
        }

    # ── Anthropic via CF gateway ──────────────────────────────────────────────
    if provider == "anthropic":
        if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("YOUR_"):
            raise ValueError("ANTHROPIC_API_KEY required for anthropic/* models via CF gateway")

        model_id = model.replace("anthropic/", "")
        url = f"{_gateway_base()}/anthropic/v1/messages"

        headers = {
            "Authorization": f"Bearer {ANTHROPIC_API_KEY}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        if CF_TOKEN_CLAUDE:
            headers["cf-aig-authorization"] = f"Bearer {CF_TOKEN_CLAUDE}"

        # Separate system message
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]

        payload = {
            "model": model_id,
            "max_tokens": max_tokens,
            "messages": user_messages,
        }
        if system_msg:
            payload["system"] = system_msg

        logger.info("CF Gateway → Anthropic: %s", model_id)
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data.get("content", [{}])[0].get("text", "")
        return {
            "content": content,
            "model": model,
            "provider": "cf_gateway_anthropic",
            "usage": data.get("usage", {}),
        }

    # ── Workers AI (free CF native models) ───────────────────────────────────
    # Use any available CF token
    cf_token = CF_TOKEN_GPT or CF_TOKEN_CLAUDE
    if not cf_token:
        raise ValueError("CF_TOKEN_GPT or CF_TOKEN_CLAUDE required for Workers AI")

    url = _workers_ai_url(model)
    headers = {
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": "application/json",
    }
    payload = {"messages": messages, "max_tokens": max_tokens}

    logger.info("CF Workers AI: %s", model)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    result = data.get("result", data)
    content = result.get("response", result.get("content", ""))
    return {
        "content": content,
        "model": model,
        "provider": "cf_workers_ai",
        "usage": result.get("usage", {}),
    }


# ── LangChain-compatible wrapper ──────────────────────────────────────────────

class CloudflareAI:
    """LangChain-compatible wrapper. Drop-in for ChatGroq/ChatAnthropic."""

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
        normalised = []
        for m in messages:
            if hasattr(m, "type") and hasattr(m, "content"):
                role = {"human": "user", "ai": "assistant", "system": "system"}.get(m.type, m.type)
                normalised.append({"role": role, "content": m.content})
            elif isinstance(m, dict):
                normalised.append(m)

        result = await run(
            model=self.model,
            messages=normalised,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        class _Response:
            def __init__(self, content: str):
                self.content = content
                self.response_metadata: dict = {}

        return _Response(result["content"])
