#!/usr/bin/env python3
"""
Verify all LLM models in the router
Tests model availability and configuration
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.llm_router import (
    GROQ_MODELS,
    CEREBRAS_MODELS,
    TOGETHER_MODELS,
    HF_MODELS,
    OPENROUTER_MODELS,
    GOOGLE_MODELS,
    providers,
    select,
)


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def verify_models():
    """Verify all models in the router"""
    
    print_section("TILLU LLM Router - Model Verification")
    
    # Check provider availability
    print("Provider Availability:")
    p = providers()
    for provider, available in p.items():
        status = "✅ AVAILABLE" if available else "❌ NOT CONFIGURED"
        print(f"  {provider:15} {status}")
    
    # Verify model specs
    print_section("Model Specifications")
    
    models_by_provider = {
        "Groq": GROQ_MODELS,
        "Cerebras": CEREBRAS_MODELS,
        "Together AI": TOGETHER_MODELS,
        "HuggingFace": HF_MODELS,
        "OpenRouter": OPENROUTER_MODELS,
        "Google Gemini": GOOGLE_MODELS,
    }
    
    total_models = 0
    for provider_name, models in models_by_provider.items():
        print(f"\n{provider_name}:")
        for task, model in models.items():
            print(f"  {task:15} → {model}")
            total_models += 1
    
    print_section("Task Routing Verification")
    
    tasks = [
        "quick_chat",
        "quality_chat",
        "empathy",
        "deep_reasoning",
        "research",
        "coding",
        "analysis",
        "image_generation",
        "multimodal",
    ]
    
    languages = ["en", "hi"]
    
    for lang in languages:
        print(f"\nLanguage: {lang}")
        for task in tasks:
            try:
                selection = select(task, lang)
                provider = selection["provider"]
                model = selection["model"]
                print(f"  {task:20} → {provider:12} / {model}")
            except Exception as e:
                print(f"  {task:20} → ❌ ERROR: {str(e)[:50]}")
    
    print_section("Summary")
    
    print(f"Total Models Configured: {total_models}")
    print(f"Total Providers: {len(models_by_provider)}")
    print(f"Available Providers: {sum(1 for v in p.values() if v)}")
    print(f"Tasks Supported: {len(tasks)}")
    print(f"Languages Supported: {len(languages)}")
    
    print("\n✅ Model verification complete!")
    print("\nNext steps:")
    print("  1. Add Cloudflare Workers AI models")
    print("  2. Test each provider with sample requests")
    print("  3. Monitor latency and accuracy")


if __name__ == "__main__":
    verify_models()
