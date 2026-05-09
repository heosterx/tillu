"""
TILLU LLM Router
=================
Selects the best available LLM provider based on:
  - Task type (speed vs depth vs creativity)
  - Provider availability (API key configured)
  - Priority order per task

Provider priority:
  quick_chat      → Groq 8B → CF Llama → Cerebras
  deep_reasoning  → Cerebras 70B → CF Claude → Groq 70B
  creative        → CF Claude → Groq 70B → OpenRouter
  empathy         → CF Claude → Groq 70B
  coding          → CF Claude → OpenRouter DeepSeek → Groq 70B
  analysis        → Cerebras → CF Claude → Groq 70B
"""

from __future__ import annotations

import os
from typing import Any

from app.utils.logging import get_logger

logger = get_logger("llm_router")

# ── Provider availability check ───────────────────────────────────────────────

def _has(key: str) -> bool:
    val = os.environ.get(key, "")
    return bool(val and not val.startswith("YOUR_"))


def available_providers() -> dict[str, bool]:
    return {
        "groq":       _has("GROQ_API_KEY"),
        "cerebras":   _has("CEREBRAS_API_KEY"),
        "cloudflare": _has("CF_API_TOKEN") and _has("CF_ACCOUNT_ID"),
        "openrouter": _has("OPENROUTER_API_KEY"),
        "google":     _has("GOOGLE_API_KEY"),
        "openai":     _has("OPENAI_API_KEY"),
        "anthropic":  _has("ANTHROPIC_API_KEY"),
    }


# ── Model selection ───────────────────────────────────────────────────────────

def select_model(
    task: str = "quick_chat",
    word_count: int = 0,
) -> dict[str, Any]:
    """
    Select the best model + provider for a given task.

    Returns:
        {
            "provider": "groq" | "cerebras" | "cloudflare" | ...,
            "model":    model identifier string,
            "client":   "groq" | "cf" | "cerebras" | "openrouter",
        }
    """
    avail = available_providers()

    # ── Deep reasoning / analysis ─────────────────────────────────────────────
    if task in ("deep_reasoning", "analysis", "research"):
        if avail["cerebras"]:
            return {"provider": "cerebras", "model": "llama-3.3-70b", "client": "cerebras"}
        if avail["cloudflare"]:
            return {"provider": "cloudflare", "model": "anthropic/claude-opus-4.6", "client": "cf"}
        if avail["groq"]:
            return {"provider": "groq", "model": "llama-3.1-70b-versatile", "client": "groq"}

    # ── Empathy / emotional support ───────────────────────────────────────────
    if task == "empathy":
        if avail["cloudflare"]:
            return {"provider": "cloudflare", "model": "anthropic/claude-opus-4.6", "client": "cf"}
        if avail["groq"]:
            return {"provider": "groq", "model": "llama-3.1-70b-versatile", "client": "groq"}

    # ── Creative / long-form ──────────────────────────────────────────────────
    if task in ("creative", "long_form"):
        if avail["cloudflare"]:
            return {"provider": "cloudflare", "model": "anthropic/claude-opus-4.6", "client": "cf"}
        if avail["groq"]:
            return {"provider": "groq", "model": "llama-3.1-70b-versatile", "client": "groq"}

    # ── Coding ────────────────────────────────────────────────────────────────
    if task == "coding":
        if avail["cloudflare"]:
            return {"provider": "cloudflare", "model": "anthropic/claude-opus-4.6", "client": "cf"}
        if avail["openrouter"]:
            return {"provider": "openrouter", "model": "deepseek/deepseek-coder-v2", "client": "openrouter"}
        if avail["groq"]:
            return {"provider": "groq", "model": "llama-3.1-70b-versatile", "client": "groq"}

    # ── Quick chat (default) ──────────────────────────────────────────────────
    # Use quality model for longer inputs
    if word_count > 50 and avail["groq"]:
        return {"provider": "groq", "model": "llama-3.1-70b-versatile", "client": "groq"}

    if avail["groq"]:
        return {"provider": "groq", "model": "llama-3.1-8b-instant", "client": "groq"}

    # ── Fallbacks ─────────────────────────────────────────────────────────────
    if avail["cloudflare"]:
        return {
            "provider": "cloudflare",
            "model": "@cf/meta/llama-3.1-8b-instruct",
            "client": "cf",
        }
    if avail["google"]:
        return {"provider": "google", "model": "gemini-1.5-flash", "client": "google"}

    raise RuntimeError(
        "No LLM provider configured. Set at least GROQ_API_KEY or CF_API_TOKEN+CF_ACCOUNT_ID."
    )


async def invoke(
    task: str,
    messages: list[dict],
    word_count: int = 0,
    max_tokens: int = 1024,
    temperature: float = 0.75,
) -> dict[str, Any]:
    """
    Route and invoke the best available LLM.

    Returns:
        {"content": str, "model": str, "provider": str}
    """
    selection = select_model(task, word_count)
    provider  = selection["provider"]
    model     = selection["model"]
    client    = selection["client"]

    logger.info("LLM route: task=%s → provider=%s model=%s", task, provider, model)

    # ── Cloudflare ────────────────────────────────────────────────────────────
    if client == "cf":
        from app.providers.cloudflare_ai import run as cf_run
        result = await cf_run(model=model, messages=messages, max_tokens=max_tokens)
        return result

    # ── Groq ──────────────────────────────────────────────────────────────────
    if client == "groq":
        from langchain_groq import ChatGroq
        from langchain.schema import HumanMessage, SystemMessage, AIMessage
        import os

        llm = ChatGroq(
            api_key=os.environ["GROQ_API_KEY"],
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        lc_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        response = await llm.ainvoke(lc_messages)
        return {"content": response.content, "model": model, "provider": "groq"}

    # ── Cerebras ──────────────────────────────────────────────────────────────
    if client == "cerebras":
        import httpx, os
        r = await httpx.AsyncClient(timeout=60).post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['CEREBRAS_API_KEY']}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return {"content": content, "model": model, "provider": "cerebras"}

    raise RuntimeError(f"Unknown client: {client}")
