"""
Cloudflare AI Gateway Provider
================================
Supports all models available via CF AI Gateway:
  - openai/gpt-5.5-pro          (OpenAI via gateway)
  - anthropic/claude-opus-4.6   (Anthropic via gateway)
  - @cf/meta/llama-3.1-8b-instruct  (Workers AI native — free)
  - @cf/meta/llama-3.3-70b-instruct (Workers AI native — free)

Two call patterns supported:
  1. messages: [{role, content}]  — chat completions style
  2. input: "string"              — Workers AI simple style

Environment variables:
  CF_API_TOKEN    — cfut_... token from dash.cloudflare.com/profile/api-tokens
  CF_ACCOUNT_ID   — 32-char hex from dash.cloudflare.com right sidebar
  CF_GATEWAY_ID   — AI Gateway name (default: "default")
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

# ── URL builders ──────────────────────────────────────────────────────────────

def _gateway_base() -> str:
    return f"https://gateway.ai.cloudflare.com/v1/{CF_ACCOUNT_ID}/{CF_GATEWAY_ID}"


def _workers_ai_url(model: str) -> str:
    return f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{model}"


def _provider_from_model(model: str) -> str:
    """Detect provider slug from model string."""
    if model.startswith("openai/") or model.startswith("gpt-"):
        return "openai"
    if model.startswith("anthropic/") or model.startswith("claude-"):
        return "anthropic"
    if model.startswith("@cf/") or model.startswith("@hf/"):
        return "workers-ai"
    if model.startswith("google/") or model.startswith("gemini-"):
        return "google-ai-studio"
    if model.startswith("mistral/"):
        return "mistral"
    return "workers-ai"


# ── Main async run function ───────────────────────────────────────────────────

async def run(
    model: str,
    messages: list[dict[str, str]] | None = None,
    input: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """
    Run any model via Cloudflare AI Gateway.

    Supports both call styles:
      run(model, messages=[{"role":"user","content":"..."}])
      run(model, input="What are the three laws of thermodynamics?")

    Args:
        model:      e.g. "openai/gpt-5.5-pro", "anthropic/claude-opus-4.6",
                    "@cf/meta/llama-3.1-8b-instruct"
        messages:   Chat messages list (OpenAI style)
        input:      Simple string input (Workers AI style)
        max_tokens: Max tokens to generate
        temperature: Sampling temperature

    Returns:
        {"content": str, "model": str, "provider": str, "usage": dict}
    """
    if not CF_API_TOKEN or not CF_ACCOUNT_ID:
        raise ValueError(
            "CF_API_TOKEN and CF_ACCOUNT_ID must be set.\n"
            "Get Account ID from: dash.cloudflare.com → right sidebar"
        )

    # Normalise: if only input string given, convert to messages
    if input and not messages:
        messages = [{"role": "user", "content": input}]
    if not messages:
        raise ValueError("Provide either messages or input")

    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    provider = _provider_from_model(model)

    # ── OpenAI models via gateway ─────────────────────────────────────────────
    if provider == "openai":
        model_id = model.replace("openai/", "")
        url = f"{_gateway_base()}/openai/chat/completions"
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data["choices"][0]["message"]["content"]
        return {
            "content": content,
            "model": model,
            "provider": "cloudflare_gateway_openai",
            "usage": data.get("usage", {}),
        }

    # ── Anthropic models via gateway ──────────────────────────────────────────
    if provider == "anthropic":
        model_id = model.replace("anthropic/", "")
        url = f"{_gateway_base()}/anthropic/v1/messages"
        # Separate system message if present
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_messages = [m for m in messages if m["role"] != "system"]
        payload = {
            "model": model_id,
            "max_tokens": max_tokens,
            "messages": user_messages,
        }
        if system_msg:
            payload["system"] = system_msg

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        content = data.get("content", [{}])[0].get("text", "")
        return {
            "content": content,
            "model": model,
            "provider": "cloudflare_gateway_anthropic",
            "usage": data.get("usage", {}),
        }

    # ── Workers AI native models ──────────────────────────────────────────────
    # Use gateway URL if gateway is configured, else direct Workers AI
    if CF_GATEWAY_ID:
        url = f"{_gateway_base()}/workers-ai/{model}"
    else:
        url = _workers_ai_url(model)

    # Workers AI supports both messages and input formats
    payload = {
        "messages": messages,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    # Workers AI wraps in {"result": {"response": "..."}}
    result = data.get("result", data)
    content = result.get("response", result.get("content", ""))

    return {
        "content": content,
        "model": model,
        "provider": "cloudflare_workers_ai",
        "usage": result.get("usage", {}),
    }


# ── LangChain-compatible wrapper ──────────────────────────────────────────────

class CloudflareAI:
    """
    LangChain-compatible wrapper for Cloudflare AI Gateway.
    Drop-in for ChatGroq / ChatAnthropic in TILLU chains.

    Usage:
        llm = CloudflareAI(model="openai/gpt-5.5-pro")
        response = await llm.ainvoke(messages)
        print(response.content)
    """

    def __init__(
        self,
        model: str = "openai/gpt-5.5-pro",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def ainvoke(self, messages: list) -> Any:
        """Invoke model. Accepts LangChain message objects or plain dicts."""
        normalised = []
        for m in messages:
            if hasattr(m, "type") and hasattr(m, "content"):
                role = {
                    "human": "user",
                    "ai": "assistant",
                    "system": "system",
                }.get(m.type, m.type)
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
