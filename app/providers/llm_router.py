"""
TILLU Universal LLM Router
============================
Single entry point for ALL LLM providers (Free tier only).
Automatically selects the best available model per task.

Providers integrated (in priority order per task):
  1. Groq          — fastest, free 14.4k tokens/min
  2. Cerebras      — deep reasoning, free ~500 req/day
  3. Together AI   — Meta Llama 3.3 70B, DeepSeek R1, FLUX.1 image gen
  4. Cloudflare    — @cf/meta/llama-2-7b-chat-int8, @cf/mistral/mistral-7b-instruct-v0.1
  5. HF Inference  — 13 free models via router.huggingface.co
  6. OpenRouter    — 200+ models, 200 free req/day
  7. Google Gemini — multimodal, 1500 free req/day

Task → Provider mapping:
  quick_chat      → Groq 8B → Together Llama 3.3 → CF Llama 2 → HF Gemma
  quality_chat    → Groq 70B → Together Llama 3.3 → CF Mistral → Cerebras
  empathy         → Groq 70B → Together Llama 3.3 → CF Mistral → Cerebras
  deep_reasoning  → Together DeepSeek-R1 → Cerebras → Groq 70B
  research        → Together DeepSeek-R1 → Cerebras → Groq 70B
  coding          → Together Llama 3.3 → HF Qwen-Coder → Groq 70B
  analysis        → Together DeepSeek-R1 → Cerebras → Groq 70B
  creative        → Groq 70B → Together Llama 3.3 → CF Mistral → HF Gemma
  multimodal      → Google Gemini Flash
  image_gen       → Together FLUX.1 [schnell]
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
        "together":   _has("TOGETHER_API_KEY"),
        "cloudflare": _has("CLOUDFLARE_API_TOKEN") and _has("CLOUDFLARE_ACCOUNT_ID"),
        "hf":         _has("HF_TOKEN"),
        "openrouter": _has("OPENROUTER_API_KEY"),
        "google":     _has("GOOGLE_API_KEY"),
    }


# ── Model specs per provider ──────────────────────────────────────────────────

GROQ_MODELS = {
    "fast":    "llama-3.1-8b-instant",
    "quality": "llama-3.1-70b-versatile",
    "coding":  "llama-3.1-70b-versatile",
}

CEREBRAS_MODELS = {
    "fast":    "llama3.1-8b",
    "quality": "qwen-3-235b-a22b-instruct-2507",
}

TOGETHER_MODELS = {
    "fast":      "meta-llama/Llama-3.3-8B-Instruct-Turbo",
    "quality":   "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "deep":      "deepseek-ai/DeepSeek-R1",
    "image":     "black-forest-labs/FLUX.1-schnell",
}

CLOUDFLARE_MODELS = {
    "fast":    "@cf/meta/llama-2-7b-chat-int8",
    "quality": "@cf/mistral/mistral-7b-instruct-v0.1",
    "coding":  "@cf/mistral/mistral-7b-instruct-v0.1",
}

HF_MODELS = {
    "fastest":  "Qwen/Qwen3-8B",
    "fast":     "google/gemma-3-27b-it",
    "quality":  "meta-llama/Llama-3.3-70B-Instruct",
    "reasoning":"deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "deep":     "deepseek-ai/DeepSeek-R1",
    "coding":   "Qwen/Qwen2.5-Coder-32B-Instruct",
    "analysis": "deepseek-ai/DeepSeek-V3-0324",
    "hindi":    "google/gemma-3-27b-it",
}

OPENROUTER_MODELS = {
    "free":    "meta-llama/llama-3.1-8b-instruct:free",
    "quality": "meta-llama/llama-3.3-70b-instruct:free",
    "coding":  "deepseek/deepseek-coder-v2:free",
}

GOOGLE_MODELS = {
    "fast":      "gemini-2.5-flash",
    "quality":   "gemini-2.5-pro",
    "multimodal":"gemini-2.5-flash-lite",
}


def select(task: str = "quick_chat", lang: str = "en") -> dict[str, Any]:
    """Select best provider + model for a task."""
    p = providers()

    if lang == "hi" and p["hf"]:
        return {"provider": "hf", "model": HF_MODELS["hindi"], "client": "hf"}

    if task in ("quick_chat", "small_talk", "general_query", "follow_up"):
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["fast"], "client": "groq"}
        if p["together"]:
            return {"provider": "together", "model": TOGETHER_MODELS["fast"], "client": "together"}
        if p["cloudflare"]:
            return {"provider": "cloudflare", "model": CLOUDFLARE_MODELS["fast"], "client": "cloudflare"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["fastest"], "client": "hf"}

    if task in ("quality_chat", "empathy", "creative", "long_form"):
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}
        if p["together"]:
            return {"provider": "together", "model": TOGETHER_MODELS["quality"], "client": "together"}
        if p["cloudflare"]:
            return {"provider": "cloudflare", "model": CLOUDFLARE_MODELS["quality"], "client": "cloudflare"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["quality"], "client": "hf"}

    if task in ("deep_reasoning", "research"):
        if p["together"]:
            return {"provider": "together", "model": TOGETHER_MODELS["reasoning"], "client": "together"}
        if p["cerebras"]:
            return {"provider": "cerebras", "model": CEREBRAS_MODELS["quality"], "client": "cerebras"}
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}

    if task == "analysis":
        if p["together"]:
            return {"provider": "together", "model": TOGETHER_MODELS["reasoning"], "client": "together"}
        if p["cerebras"]:
            return {"provider": "cerebras", "model": CEREBRAS_MODELS["quality"], "client": "cerebras"}
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}

    if task == "coding":
        if p["together"]:
            return {"provider": "together", "model": TOGETHER_MODELS["quality"], "client": "together"}
        if p["hf"]:
            return {"provider": "hf", "model": HF_MODELS["coding"], "client": "hf"}
        if p["groq"]:
            return {"provider": "groq", "model": GROQ_MODELS["quality"], "client": "groq"}

    if task == "image_generation":
        if p["together"]:
            return {"provider": "together", "model": TOGETHER_MODELS["image"], "client": "together"}

    if task == "multimodal":
        if p["google"]:
            return {"provider": "google", "model": GOOGLE_MODELS["multimodal"], "client": "google"}

    for provider, model, client in [
        ("groq",       GROQ_MODELS["fast"],       "groq"),
        ("together",   TOGETHER_MODELS["fast"],   "together"),
        ("cloudflare", CLOUDFLARE_MODELS["fast"], "cloudflare"),
        ("hf",         HF_MODELS["fastest"],      "hf"),
        ("cerebras",   CEREBRAS_MODELS["fast"],   "cerebras"),
        ("openrouter", OPENROUTER_MODELS["free"], "openrouter"),
        ("google",     GOOGLE_MODELS["fast"],     "google"),
    ]:
        if p.get(provider):
            return {"provider": provider, "model": model, "client": client}

    raise RuntimeError(
        "No LLM provider configured.\n"
        "Set at least GROQ_API_KEY (free at console.groq.com), TOGETHER_API_KEY (free at together.ai), or HF_TOKEN."
    )


async def invoke(
    messages: list[dict],
    task: str = "quick_chat",
    lang: str = "en",
    max_tokens: int = 1024,
    temperature: float = 0.75,
    model_override: str | None = None,
    provider_override: str | None = None,
) -> dict[str, Any]:
    """Route and invoke the best LLM for the task."""
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

    elif client == "together":
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['TOGETHER_API_KEY']}",
                         "Content-Type": "application/json"},
                json={"model": model, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature},
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]

    elif client == "cloudflare":
        async with httpx.AsyncClient(timeout=60) as c:
            account_id = os.environ['CLOUDFLARE_ACCOUNT_ID']
            api_token = os.environ['CLOUDFLARE_API_TOKEN']
            r = await c.post(
                f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}",
                headers={"Authorization": f"Bearer {api_token}",
                         "Content-Type": "application/json"},
                json={"messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            )
            r.raise_for_status()
            result = r.json()
            if "result" in result and "response" in result["result"]:
                content = result["result"]["response"]
            else:
                content = result.get("result", {}).get("response", "No response")

    elif client == "hf":
        from app.providers.hf_inference import chat as hf_chat
        result = await hf_chat(messages=messages, model=model, max_tokens=max_tokens,
                               temperature=temperature)
        content = result["content"]

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

    elif client == "google":
        async with httpx.AsyncClient(timeout=60) as c:
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


class TilluLLM:
    """Universal LangChain-compatible LLM wrapper."""

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
