"""
TILLU Universal LLM Router
============================
Single entry point for ALL LLM providers.
Automatically selects the best available model per task.

Providers integrated (in priority order per task):
  1. Groq          — fastest, free 14.4k tokens/min
  2. Cerebras      — deep reasoning, free ~500 req/day
  3. HF Inference  — 13 free models via router.huggingface.co
  4. OpenRouter    — 200+ models, 200 free req/day
  5. Google Gemini — multimodal, 1500 free req/day
  6. OpenAI        — GPT models (needs credits)
  7. Anthropic     — Claude models (needs credits)

Task → Provider mapping:
  quick_chat      → Groq 8B → HF Gemma → HF Qwen
  quality_chat    → Groq 70B → HF Llama-70B → Cerebras
  empathy         → Groq 70B → HF Gemma → Cerebras
  deep_reasoning  → Cerebras → HF DeepSeek-R1 → Groq 70B
  research        → Cerebras → HF DeepSeek-V3 → Groq 70B
  coding          → HF Qwen-Coder → HF DeepSeek-V3 → Groq 70B
  analysis        → Cerebras → HF DeepSeek-V3 → Groq 70B
  creative        → Groq 70B → HF Gemma → OpenRouter
  multimodal      → Google Gemini Flash
  hindi_primary   → HF Gemma-3-27B → Groq 70B (best Hinglish)
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.utils.logging import get_logger

logger = get_logger("llm_router")

# ── Provider availability ─────────────────────────────────────────────────────

def _has(key: str) -> bool:
    v = os.environ.get(key, "")
    return bool(v and not v.startswith("YOUR_") and not v.startswith("sk-YOUR"))


def providers() -> dict[str, bool]:
    return {
        "groq":       _has("GROQ_API_KEY"),
        "cerebras":   _has("CEREBRAS_API_KEY"),
        "hf":         _has("HF_TOKEN"),
        "openrouter": _has("OPENROUTER_API_KEY"),
        "google":     _has("GOOGLE_API_KEY"),
    
    }


# ── Model specs per provider ──────────────────────────────────────────────────

GROQ_MODELS = {
    "fast":    "llama-3.1-8b-instant",       # ~200ms, 14.4k tok/min
    "quality": "llama-3.1-70b-versatile",    # ~700ms, 6k tok/min
    "coding":  "llama-3.1-70b-versatile",
}

CEREBRAS_MODELS = {
    "fast":    "llama3.1-8b",                # ~100ms, ultra-fast
    "quality": "qwen-3-235b-a22b-instruct-2507",  # best available
}

HF_MODELS = {
    "fastest":  "Qwen/Qwen3-8B",                           # 0.9s
    "fast":     "google/gemma-3-27b-it",                   # 2.9s, best Hinglish
    "quality":  "meta-llama/Llama-3.3-70B-Instruct",       # 6.4s
    "reasoning":"deepseek-ai/DeepSeek-R1-Distill-Llama-70B",# 1.1s
    "deep":     "deepseek-ai/DeepSeek-R1",                 # 4.5s
    "coding":   "Qwen/Qwen2.5-Coder-32B-Instruct",         # 7.4s
    "analysis": "deepseek-ai/DeepSeek-V3-0324",            # 6.0s
    "hindi":    "google/gemma-3-27b-it",                   # best Hinglish
}

OPENROUTER_MODELS = {
    "free":    "meta-llama/llama-3.1-8b-instruct:free",
    "quality": "meta-llama/llama-3.3-70b-instruct:free",
    "coding":  "deepseek/deepseek-coder-v2:free",
}

GOOGLE_MODELS = {
    "fast":      "gemini-1.5-flash",
    "quality":   "gemini-1.5-pro",
    "multimodal":"gemini-1.5-flash",
}


# ── Task → model selection ────────────────────────────────────────────────────

def select(task: str = "quick_chat", lang: str = "en") -> dict[str, Any]:
    """
    Select best provider + model for a task.
    Returns {"provider", "model", "client"}.
    """
    p = providers()

    # Hindi-primary: HF Gemma is best for Hinglish
    if lang == "hi" and p["hf"]:
        return {"provider": "hf", "model": HF_MODELS["hindi"], "client": "hf"}

    # ── quick_chat ────────────────────────────────────────────────────────────
    if task in ("quick_chat", "small_talk", "general_query", "follow_up"):
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["fast"], "client": "groq"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["fastest"], "client": "hf"}
        if p["cerebras"]:
            return {"provider": "cerebras", "model": CEREBRAS_MODELS["fast"], "client": "cerebras"}

    # ── quality_chat / empathy ────────────────────────────────────────────────
    if task in ("quality_chat", "empathy", "creative", "long_form"):
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["quality"], "client": "hf"}
        if p["cerebras"]:
            return {"provider": "cerebras", "model": CEREBRAS_MODELS["quality"], "client": "cerebras"}

    # ── deep_reasoning / research ─────────────────────────────────────────────
    if task in ("deep_reasoning", "research"):
        if p["cerebras"]:
            return {"provider": "cerebras", "model": CEREBRAS_MODELS["quality"], "client": "cerebras"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["reasoning"], "client": "hf"}
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}

    # ── analysis ──────────────────────────────────────────────────────────────
    if task == "analysis":
        if p["cerebras"]:
            return {"provider": "cerebras", "model": CEREBRAS_MODELS["quality"], "client": "cerebras"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["analysis"], "client": "hf"}
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}

    # ── coding ────────────────────────────────────────────────────────────────
    if task == "coding":
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["coding"], "client": "hf"}
        if p["openrouter"]:
            return {"provider": "openrouter", "model": OPENROUTER_MODELS["coding"], "client": "openrouter"}
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}

    # ── multimodal ────────────────────────────────────────────────────────────
    if task == "multimodal":
        if p["google"]:
            return {"provider": "google", "model": GOOGLE_MODELS["multimodal"], "client": "google"}

    # ── Universal fallback chain ──────────────────────────────────────────────
    for provider, model, client in [
        ("groq",       GROQ_MODELS["fast"],       "groq"),
        ("hf",         HF_MODELS["fastest"],       "hf"),
        ("cerebras",   CEREBRAS_MODELS["fast"],    "cerebras"),
        ("openrouter", OPENROUTER_MODELS["free"],  "openrouter"),
        ("google",     GOOGLE_MODELS["fast"],      "google"),
    ]:
        if p.get(provider):
            return {"provider": provider, "model": model, "client": client}

    raise RuntimeError(
        "No LLM provider configured.\n"
        "Set at least GROQ_API_KEY (free at console.groq.com) or HF_TOKEN."
    )


# ── Universal invoke ──────────────────────────────────────────────────────────

async def invoke(
    messages: list[dict],
    task: str = "quick_chat",
    lang: str = "en",
    max_tokens: int = 1024,
    temperature: float = 0.75,
    model_override: str | None = None,
    provider_override: str | None = None,
) -> dict[str, Any]:
    """
    Route and invoke the best LLM for the task.

    Args:
        messages:          OpenAI-style message list
        task:              Task type for routing
        lang:              "hi" | "en" | "auto"
        max_tokens:        Max tokens
        temperature:       Sampling temperature
        model_override:    Force a specific model ID
        provider_override: Force a specific provider

    Returns:
        {"content": str, "model": str, "provider": str, "latency_ms": int}
    """
    import time
    t0 = time.time()

    if provider_override and model_override:
        sel = {"provider": provider_override, "model": model_override, "client": provider_override}
    else:
        sel = select(task, lang)
        if model_override:
            sel["model"] = model_override

    provider = sel["provider"]
    model    = sel["model"]
    client   = sel["client"]

    logger.info("LLM route: task=%s lang=%s → %s/%s", task, lang, provider, model)

    content = ""

    # ── Groq ──────────────────────────────────────────────────────────────────
    if client == "groq":
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}",
                         "Content-Type": "application/json"},
                json={"model": model, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature},
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]

    # ── Cerebras ──────────────────────────────────────────────────────────────
    elif client == "cerebras":
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['CEREBRAS_API_KEY']}"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens,
                      "temperature": temperature},
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]

    # ── HF Inference ──────────────────────────────────────────────────────────
    elif client == "hf":
        from app.providers.hf_inference import chat as hf_chat
        result = await hf_chat(messages=messages, model=model, max_tokens=max_tokens,
                               temperature=temperature)
        content = result["content"]

    # ── OpenRouter ────────────────────────────────────────────────────────────
    elif client == "openrouter":
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "HTTP-Referer": "https://tillu.ai",
                    "X-Title": "TILLU Personal AI",
                },
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]

    # ── Google Gemini ─────────────────────────────────────────────────────────
    elif client == "google":
        async with httpx.AsyncClient(timeout=60) as c:
            # Convert to Gemini format
            gemini_msgs = [{"role": "user" if m["role"] != "assistant" else "model",
                           "parts": [{"text": m["content"]}]} for m in messages
                          if m["role"] != "system"]
            system = next((m["content"] for m in messages if m["role"] == "system"), None)
            payload: dict = {"contents": gemini_msgs,
                            "generationConfig": {"maxOutputTokens": max_tokens,
                                                 "temperature": temperature}}
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": os.environ["GOOGLE_API_KEY"]},
                json=payload,
            )
            r.raise_for_status()
            content = r.json()["candidates"][0]["content"]["parts"][0]["text"]

    # ── OpenAI ────────────────────────────────────────────────────────────────
    elif client == "openai":
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens},
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]

    # ── Anthropic ─────────────────────────────────────────────────────────────
    elif client == "anthropic":
        system = next((m["content"] for m in messages if m["role"] == "system"), None)
        user_msgs = [m for m in messages if m["role"] != "system"]
        async with httpx.AsyncClient(timeout=60) as c:
            payload = {"model": model, "max_tokens": max_tokens, "messages": user_msgs}
            if system:
                payload["system"] = system
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                         "anthropic-version": "2023-06-01"},
                json=payload,
            )
            r.raise_for_status()
            content = r.json()["content"][0]["text"]

    else:
        raise RuntimeError(f"Unknown client: {client}")

    latency_ms = int((time.time() - t0) * 1000)
    logger.info("LLM response: %s/%s in %dms", provider, model, latency_ms)

    return {
        "content": content,
        "model": model,
        "provider": provider,
        "latency_ms": latency_ms,
    }


# ── LangChain-compatible wrapper ──────────────────────────────────────────────

class TilluLLM:
    """
    Universal LangChain-compatible LLM wrapper.
    Automatically routes to the best available provider.

    Usage:
        llm = TilluLLM(task="quality_chat", lang="hi")
        response = await llm.ainvoke(messages)
        print(response.content)
    """

    def __init__(
        self,
        task: str = "quick_chat",
        lang: str = "en",
        max_tokens: int = 1024,
        temperature: float = 0.75,
        model: str | None = None,
        provider: str | None = None,
    ):
        self.task = task
        self.lang = lang
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.model = model
        self.provider = provider

    async def ainvoke(self, messages: list) -> Any:
        normalised = []
        for m in messages:
            if hasattr(m, "type") and hasattr(m, "content"):
                role = {"human": "user", "ai": "assistant", "system": "system"}.get(m.type, m.type)
                normalised.append({"role": role, "content": m.content})
            elif isinstance(m, dict):
                normalised.append(m)

        result = await invoke(
            messages=normalised,
            task=self.task,
            lang=self.lang,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            model_override=self.model,
            provider_override=self.provider,
        )

        class _Response:
            def __init__(self, r: dict):
                self.content = r["content"]
                self.response_metadata = {
                    "model": r["model"],
                    "provider": r["provider"],
                    "latency_ms": r["latency_ms"],
                }

        return _Response(result)
