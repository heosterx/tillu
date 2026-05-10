"""
TILLU AI Providers
==================
Universal LLM routing across all providers.

Usage:
    from app.providers import invoke, TilluLLM, providers

    # Auto-route to best available provider
    result = await invoke(messages, task="quality_chat", lang="hi")

    # LangChain-compatible wrapper
    llm = TilluLLM(task="coding")
    response = await llm.ainvoke(messages)
"""
from app.providers.llm_router import invoke, TilluLLM, select, providers
from app.providers.hf_inference import HFInference, chat as hf_chat, ALL_MODELS as HF_MODELS

__all__ = [
    # Universal router
    "invoke",
    "TilluLLM",
    "select",
    "providers",
    # HF specific
    "HFInference",
    "hf_chat",
    "HF_MODELS",
]
