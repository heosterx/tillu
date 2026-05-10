"""
HuggingFace Inference Providers
=================================
Free serverless LLM inference via router.huggingface.co
OpenAI-compatible chat completions endpoint.

All models confirmed working (tested 2026-05-10):

FAST (< 3s):
  Qwen/Qwen3-8B                              ~0.9s  — fastest, thinking model
  deepseek-ai/DeepSeek-R1-Distill-Llama-70B  ~1.1s  — fast reasoning
  meta-llama/Llama-3.2-1B-Instruct           ~1.3s  — tiny, very fast
  Qwen/Qwen3-30B-A3B                         ~1.4s  — fast MoE
  google/gemma-3-27b-it                      ~2.9s  — great Hinglish

QUALITY (3-7s):
  meta-llama/Llama-3.1-8B-Instruct           ~5.7s  — good Hinglish
  deepseek-ai/DeepSeek-V3-0324               ~6.0s  — strong general
  meta-llama/Llama-3.3-70B-Instruct          ~6.4s  — best quality
  meta-llama/Llama-3.1-70B-Instruct          ~6.6s  — quality fallback

LARGE (7s+):
  Qwen/Qwen2.5-Coder-32B-Instruct            ~7.4s  — coding specialist
  Qwen/Qwen2.5-72B-Instruct                  ~8.6s  — large quality
  Qwen/Qwen2.5-7B-Instruct                   ~8.8s  — reliable fallback
  deepseek-ai/DeepSeek-R1                    ~4.5s  — deep reasoning (verbose)

NOT available via HF router (use CF Workers AI directly):
  @cf/zai-org/glm-4.7-flash, @cf/meta/llama-3.1-8b-instruct, etc.

Rate limits: free tier, ~1000 req/day per token
Endpoint: https://router.huggingface.co/v1/chat/completions
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.utils.logging import get_logger

logger = get_logger("hf_inference")

HF_TOKEN   = os.environ.get("HF_TOKEN", "")
ENDPOINT   = "https://router.huggingface.co/v1/chat/completions"

# ── Model registry ────────────────────────────────────────────────────────────

# Ordered by: speed first, then quality
MODELS = {
    # task → list of models in priority order (fastest first within quality tier)
    "quick_chat": [
        "Qwen/Qwen3-8B",                            # 0.9s — fastest
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B", # 1.1s — fast reasoning
        "meta-llama/Llama-3.2-1B-Instruct",          # 1.3s — tiny, very fast
        "Qwen/Qwen3-30B-A3B",                         # 1.4s — fast MoE
        "google/gemma-3-27b-it",                      # 2.9s — great Hinglish
        "meta-llama/Llama-3.1-8B-Instruct",           # 5.7s — reliable
    ],
    "quality_chat": [
        "google/gemma-3-27b-it",                      # 2.9s — great Hinglish
        "meta-llama/Llama-3.3-70B-Instruct",          # 6.4s — best quality
        "meta-llama/Llama-3.1-70B-Instruct",          # 6.6s — quality fallback
        "Qwen/Qwen2.5-72B-Instruct",                  # 8.6s — large
    ],
    "reasoning": [
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",  # 1.1s — fast reasoning
        "deepseek-ai/DeepSeek-R1",                    # 4.5s — deep reasoning
        "deepseek-ai/DeepSeek-V3-0324",               # 6.0s — strong general
        "meta-llama/Llama-3.3-70B-Instruct",          # fallback
    ],
    "coding": [
        "Qwen/Qwen2.5-Coder-32B-Instruct",            # 7.4s — coding specialist
        "deepseek-ai/DeepSeek-V3-0324",               # strong coder
        "meta-llama/Llama-3.3-70B-Instruct",          # fallback
    ],
    "analysis": [
        "deepseek-ai/DeepSeek-V3-0324",               # strong analysis
        "meta-llama/Llama-3.3-70B-Instruct",          # quality
        "Qwen/Qwen2.5-72B-Instruct",                  # large
    ],
}

# Complete verified working model list (ordered fastest → slowest)
ALL_MODELS = [
    "Qwen/Qwen3-8B",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "meta-llama/Llama-3.2-1B-Instruct",
    "Qwen/Qwen3-30B-A3B",
    "google/gemma-3-27b-it",
    "deepseek-ai/DeepSeek-R1",
    "meta-llama/Llama-3.1-8B-Instruct",
    "deepseek-ai/DeepSeek-V3-0324",
    "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/Llama-3.1-70B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
]


def is_available() -> bool:
    return bool(HF_TOKEN and not HF_TOKEN.startswith("YOUR_"))


def get_model_for_task(task: str) -> str:
    """Return the best model for a given task."""
    task_map = {
        "quick_chat":    "quick_chat",
        "small_talk":    "quick_chat",
        "general_query": "quick_chat",
        "empathy":       "quality_chat",
        "deep_reasoning":"reasoning",
        "research":      "reasoning",
        "analysis":      "analysis",
        "coding":        "coding",
        "creative":      "quality_chat",
    }
    bucket = task_map.get(task, "quick_chat")
    return MODELS[bucket][0]


# ── Core async function ───────────────────────────────────────────────────────

async def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    task: str = "quick_chat",
    max_tokens: int = 1024,
    temperature: float = 0.7,
    fallback: bool = True,
) -> dict[str, Any]:
    """
    Call HF Inference Providers with automatic model fallback.

    Args:
        messages:    OpenAI-style message list
        model:       Specific model to use (overrides task-based selection)
        task:        Task type for model selection
        max_tokens:  Max tokens to generate
        temperature: Sampling temperature
        fallback:    Try next model if current fails

    Returns:
        {"content": str, "model": str, "provider": "hf_inference"}
    """
    if not is_available():
        raise ValueError("HF_TOKEN not set")

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    # Build model priority list
    if model:
        models_to_try = [model] + (ALL_MODELS if fallback else [])
    else:
        bucket = {
            "quick_chat": "quick_chat", "small_talk": "quick_chat",
            "general_query": "quick_chat", "empathy": "quality_chat",
            "deep_reasoning": "reasoning", "research": "reasoning",
            "analysis": "analysis", "coding": "coding",
            "creative": "quality_chat",
        }.get(task, "quick_chat")
        models_to_try = MODELS[bucket] + (ALL_MODELS if fallback else [])

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_models = []
    for m in models_to_try:
        if m not in seen:
            seen.add(m)
            unique_models.append(m)

    last_error = ""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt_model in unique_models:
            try:
                logger.debug("HF Inference: %s (task=%s)", attempt_model, task)
                r = await client.post(
                    ENDPOINT,
                    headers=headers,
                    json={
                        "model": attempt_model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )

                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    logger.info("HF Inference OK: %s", attempt_model)
                    return {
                        "content": content,
                        "model": attempt_model,
                        "provider": "hf_inference",
                        "usage": r.json().get("usage", {}),
                    }

                if r.status_code == 400:
                    # Model not supported — try next
                    last_error = f"{attempt_model}: not supported"
                    continue

                if r.status_code == 429:
                    last_error = f"{attempt_model}: rate limited"
                    continue

                last_error = f"{attempt_model}: HTTP {r.status_code}"
                if not fallback:
                    break

            except httpx.TimeoutException:
                last_error = f"{attempt_model}: timeout"
                if not fallback:
                    break
                continue

    raise RuntimeError(f"All HF models failed. Last error: {last_error}")


# ── LangChain-compatible wrapper ──────────────────────────────────────────────

class HFInference:
    """LangChain-compatible wrapper for HF Inference Providers."""

    def __init__(
        self,
        model: str | None = None,
        task: str = "quick_chat",
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ):
        self.model = model
        self.task = task
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

        result = await chat(
            messages=normalised,
            model=self.model,
            task=self.task,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        class _Response:
            def __init__(self, content: str):
                self.content = content
                self.response_metadata: dict = {}

        return _Response(result["content"])
