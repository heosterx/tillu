"""
TILLU LLM Router
=================
Selects the best available LLM provider based on task type and availability.

Provider priority per task:

  quick_chat      → Groq 8B → CF Workers AI (free) → Google Gemini
  deep_reasoning  → Cerebras 70B → CF Claude (if key set) → CF GPT (if key set) → Groq 70B
  empathy         → CF Claude → CF GPT → Groq 70B → CF Workers AI
  creative        → CF Claude → CF GPT → Groq 70B
  coding          → CF GPT → CF Claude → OpenRouter DeepSeek → Groq 70B
  analysis        → Cerebras → CF Claude → CF GPT → Groq 70B

CF Workers AI (@cf/meta/llama-3.1-8b-instruct) is always available as a free fallback
as long as CF_ACCOUNT_ID and CF_TOKEN_GPT or CF_TOKEN_CLAUDE are set.

CF OpenAI/Anthropic gateway calls require the actual provider API key
(OPENAI_API_KEY / ANTHROPIC_API_KEY) in addition to the CF gateway token.
"""

from __future__ import annotations

import os
from typing import Any

from app.utils.logging import get_logger

logger = get_logger("llm_router")


def _has(key: str) -> bool:
    val = os.environ.get(key, "")
    return bool(val and not val.startswith("YOUR_") and not val.startswith("sk-YOUR"))


def available_providers() -> dict[str, bool]:
    cf_base = _has("CF_ACCOUNT_ID")
    cf_token = _has("CF_TOKEN_GPT") or _has("CF_TOKEN_CLAUDE")
    return {
        "groq":           _has("GROQ_API_KEY"),
        "cerebras":       _has("CEREBRAS_API_KEY"),
        "cf_workers":     cf_base and cf_token,                          # free, always
        "cf_openai":      cf_base and _has("OPENAI_API_KEY"),            # needs OpenAI key
        "cf_anthropic":   cf_base and _has("ANTHROPIC_API_KEY"),         # needs Anthropic key
        "openrouter":     _has("OPENROUTER_API_KEY"),
        "google":         _has("GOOGLE_API_KEY"),
    }


def select_model(task: str = "quick_chat", word_count: int = 0) -> dict[str, Any]:
    """
    Select best model + provider for a task.
    Returns {"provider", "model", "client"}.
    """
    a = available_providers()

    # ── Deep reasoning / analysis ─────────────────────────────────────────────
    if task in ("deep_reasoning", "analysis", "research"):
        if a["cerebras"]:
            return {"provider": "cerebras",     "model": "llama-3.3-70b",                    "client": "cerebras"}
        if a["cf_anthropic"]:
            return {"provider": "cf_anthropic", "model": "anthropic/claude-opus-4.6",         "client": "cf"}
        if a["cf_openai"]:
            return {"provider": "cf_openai",    "model": "openai/gpt-5.5-pro",                "client": "cf"}
        if a["groq"]:
            return {"provider": "groq",         "model": "llama-3.1-70b-versatile",           "client": "groq"}

    # ── Empathy / emotional support ───────────────────────────────────────────
    if task == "empathy":
        if a["cf_anthropic"]:
            return {"provider": "cf_anthropic", "model": "anthropic/claude-opus-4.6",         "client": "cf"}
        if a["cf_openai"]:
            return {"provider": "cf_openai",    "model": "openai/gpt-5.5-pro",                "client": "cf"}
        if a["groq"]:
            return {"provider": "groq",         "model": "llama-3.1-70b-versatile",           "client": "groq"}
        if a["cf_workers"]:
            return {"provider": "cf_workers",   "model": "@cf/meta/llama-3.1-8b-instruct",    "client": "cf"}

    # ── Creative / long-form ──────────────────────────────────────────────────
    if task in ("creative", "long_form"):
        if a["cf_anthropic"]:
            return {"provider": "cf_anthropic", "model": "anthropic/claude-opus-4.6",         "client": "cf"}
        if a["cf_openai"]:
            return {"provider": "cf_openai",    "model": "openai/gpt-5.5-pro",                "client": "cf"}
        if a["groq"]:
            return {"provider": "groq",         "model": "llama-3.1-70b-versatile",           "client": "groq"}

    # ── Coding ────────────────────────────────────────────────────────────────
    if task == "coding":
        if a["cf_openai"]:
            return {"provider": "cf_openai",    "model": "openai/gpt-5.5-pro",                "client": "cf"}
        if a["cf_anthropic"]:
            return {"provider": "cf_anthropic", "model": "anthropic/claude-opus-4.6",         "client": "cf"}
        if a["openrouter"]:
            return {"provider": "openrouter",   "model": "deepseek/deepseek-coder-v2",        "client": "openrouter"}
        if a["groq"]:
            return {"provider": "groq",         "model": "llama-3.1-70b-versatile",           "client": "groq"}

    # ── Quick chat (default) ──────────────────────────────────────────────────
    if word_count > 50 and a["groq"]:
        return {"provider": "groq",         "model": "llama-3.1-70b-versatile",               "client": "groq"}
    if a["groq"]:
        return {"provider": "groq",         "model": "llama-3.1-8b-instant",                  "client": "groq"}

    # ── Free fallbacks ────────────────────────────────────────────────────────
    if a["cf_workers"]:
        return {"provider": "cf_workers",   "model": "@cf/meta/llama-3.1-8b-instruct",        "client": "cf"}
    if a["google"]:
        return {"provider": "google",       "model": "gemini-1.5-flash",                      "client": "google"}

    raise RuntimeError(
        "No LLM provider configured.\n"
        "Set GROQ_API_KEY (free at console.groq.com) or\n"
        "CF_ACCOUNT_ID + CF_TOKEN_GPT for Workers AI (free)."
    )


async def invoke(
    task: str,
    messages: list[dict],
    word_count: int = 0,
    max_tokens: int = 1024,
    temperature: float = 0.75,
) -> dict[str, Any]:
    """Route and invoke the best available LLM for the given task."""
    sel      = select_model(task, word_count)
    provider = sel["provider"]
    model    = sel["model"]
    client   = sel["client"]

    logger.info("LLM route: task=%s → %s / %s", task, provider, model)

    # ── Cloudflare (Workers AI, OpenAI gateway, Anthropic gateway) ────────────
    if client == "cf":
        from app.providers.cloudflare_ai import run as cf_run
        result = await cf_run(model=model, messages=messages, max_tokens=max_tokens)
        return result

    # ── Groq ──────────────────────────────────────────────────────────────────
    if client == "groq":
        from langchain_groq import ChatGroq
        from langchain.schema import HumanMessage, SystemMessage, AIMessage
        llm = ChatGroq(
            api_key=os.environ["GROQ_API_KEY"],
            model_name=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        lc_msgs = []
        for m in messages:
            role, content = m.get("role", "user"), m.get("content", "")
            if role == "system":
                lc_msgs.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_msgs.append(AIMessage(content=content))
            else:
                lc_msgs.append(HumanMessage(content=content))
        response = await llm.ainvoke(lc_msgs)
        return {"content": response.content, "model": model, "provider": "groq"}

    # ── Cerebras ──────────────────────────────────────────────────────────────
    if client == "cerebras":
        import httpx
        r = await httpx.AsyncClient(timeout=60).post(
            "https://api.cerebras.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['CEREBRAS_API_KEY']}"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return {"content": content, "model": model, "provider": "cerebras"}

    raise RuntimeError(f"Unknown client: {client}")
