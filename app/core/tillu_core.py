"""
TILLU Core — Personal AI Architecture
=======================================
Single-user personal AI system designed for future extensibility.

Current capabilities:
  - Multi-provider LLM routing (Groq, Cerebras, HF, OpenRouter, Google, OpenAI, Anthropic)
  - Hindi + English (NCR Hinglish) with Indian rules enforcement
  - Persistent memory (Supabase + pgvector)
  - 16 background intelligence loops (daemon)
  - 5 n8n scheduled workflows
  - Web search + scraping
  - NLP pipeline (embeddings, emotion, similarity)

Future upgrade paths (plug-in ready):
  UI_TYPES:
    - WhatsApp (via Baileys/WA Business API)
    - Telegram Bot
    - Web App (React/Next.js)
    - Mobile App (React Native)
    - Voice (Whisper STT + TTS)
    - Desktop (Electron)

  MODEL_UPGRADES:
    - Any new Groq model → update GROQ_MODELS in llm_router.py
    - Any new HF model → run scripts/find_hf_free_models.py
    - GPT-5/Claude-4 → add OPENAI_API_KEY/ANTHROPIC_API_KEY to .env

  WORKFLOW_UPGRADES:
    - POST /internal/workflow/generate with natural language instruction
    - TILLU generates and deploys new n8n workflows autonomously
    - Weekly self-upgrade via WF-17

  MEMORY_UPGRADES:
    - pgvector already set up for semantic search
    - Add more tables to supabase/schema.sql
    - Memory consolidation runs daily at midnight IST

  INTEGRATION_UPGRADES:
    - Google Calendar/Gmail: add GOOGLE_CLIENT_ID + GMAIL_REFRESH_TOKEN
    - Notion: add NOTION_TOKEN
    - GitHub: add GITHUB_TOKEN
    - Any REST API: add to n8n workflow or daemon loop
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TilluConfig:
    """
    Runtime configuration for TILLU.
    Loaded from environment variables via app.config.settings.
    """
    # Identity
    user_name: str = "User"
    user_location: str = "NCR"          # Delhi/Noida/Gurgaon
    user_language: str = "hi+en"        # Hinglish
    timezone: str = "Asia/Kolkata"      # IST

    # Active providers (auto-detected from env)
    active_providers: list[str] = field(default_factory=list)

    # UI type (future: whatsapp, telegram, web, mobile, voice)
    ui_type: str = "api"

    # Feature flags
    memory_enabled: bool = True
    search_enabled: bool = True
    daemon_enabled: bool = True
    n8n_enabled: bool = True
    indian_rules_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_name": self.user_name,
            "user_location": self.user_location,
            "user_language": self.user_language,
            "timezone": self.timezone,
            "active_providers": self.active_providers,
            "ui_type": self.ui_type,
            "features": {
                "memory": self.memory_enabled,
                "search": self.search_enabled,
                "daemon": self.daemon_enabled,
                "n8n": self.n8n_enabled,
                "indian_rules": self.indian_rules_enabled,
            },
        }


def get_system_status() -> dict[str, Any]:
    """
    Get current system status — all providers, services, features.
    Used by health endpoints and the UI.
    """
    import os
    from app.providers.llm_router import providers

    p = providers()
    active = [k for k, v in p.items() if v]

    return {
        "tillu_version": "1.0.0",
        "architecture": "multi-provider personal AI",
        "user_focus": "Single user — NCR India",
        "language": "Hindi + English (Hinglish)",

        # Live services
        "services": {
            "nlp_space":    "https://tillu-ai-tillu-ai.hf.space",
            "daemon":       "https://tillu-ai-tillu-daemon.hf.space",
            "websearch":    "https://tillu-ai-tillu-websearch.hf.space",
            "n8n_engine":   "https://tillu-ai-tillu-engine.hf.space",
            "database":     "https://dpkmzkyzvmysvzmevhrm.supabase.co",
        },

        # LLM providers
        "llm_providers": {
            "active": active,
            "all": p,
            "priority_order": ["groq", "cerebras", "hf", "openrouter", "google", "openai", "anthropic"],
        },

        # Capabilities
        "capabilities": {
            "chat": True,
            "memory": True,
            "search": True,
            "scrape": True,
            "emotion_detection": True,
            "embeddings": True,
            "scheduled_workflows": True,
            "self_upgrade": True,
            "hindi_english": True,
            "inr_currency": True,
            "ist_timezone": True,
        },

        # Future UI types (not yet implemented)
        "future_ui_types": [
            "whatsapp",
            "telegram",
            "web_app",
            "mobile_app",
            "voice",
            "desktop",
        ],
    }
