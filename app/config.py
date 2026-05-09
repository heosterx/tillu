"""
TILLU Backend Configuration
Centralized configuration management using Pydantic Settings
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # App Configuration
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="dev-secret-key", alias="SECRET_KEY")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    
    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=4, alias="WORKERS")
    
    # Supabase
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_key: str = Field(alias="SUPABASE_KEY")
    supabase_service_key: Optional[str] = Field(default=None, alias="SUPABASE_SERVICE_KEY")
    supabase_jwt_secret: Optional[str] = Field(default=None, alias="SUPABASE_JWT_SECRET")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    upstash_redis_rest_url: Optional[str] = Field(default=None, alias="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: Optional[str] = Field(default=None, alias="UPSTASH_REDIS_REST_TOKEN")
    
    # LLM Providers
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    cerebras_api_key: Optional[str] = Field(default=None, alias="CEREBRAS_API_KEY")
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    cohere_api_key: Optional[str] = Field(default=None, alias="COHERE_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    together_api_key: Optional[str] = Field(default=None, alias="TOGETHER_API_KEY")
    
    # Hugging Face
    hf_token: Optional[str] = Field(default=None, alias="HF_TOKEN")
    hf_inference_api_url: str = Field(
        default="https://api-inference.huggingface.co",
        alias="HF_INFERENCE_API_URL"
    )
    hf_embedding_model: str = Field(
        default="sentence-transformers/all-mpnet-base-v2",
        alias="HF_EMBEDDING_MODEL"
    )
    hf_emotion_model: str = Field(
        default="j-hartmann/emotion-english-distilroberta-base",
        alias="HF_EMOTION_MODEL"
    )
    hf_classifier_model: str = Field(
        default="distilbert-base-uncased-finetuned-sst-2-english",
        alias="HF_CLASSIFIER_MODEL"
    )
    hf_summarizer_model: str = Field(
        default="facebook/bart-large-cnn",
        alias="HF_SUMMARIZER_MODEL"
    )
    hf_ner_model: str = Field(
        default="dbmdz/bert-large-cased-finetuned-conll03-english",
        alias="HF_NER_MODEL"
    )
    hf_whisper_model: str = Field(
        default="openai/whisper-medium",
        alias="HF_WHISPER_MODEL"
    )
    
    # Google OAuth (Calendar + Gmail)
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    gmail_refresh_token: Optional[str] = Field(default=None, alias="GMAIL_REFRESH_TOKEN")

    # Notion
    notion_token: Optional[str] = Field(default=None, alias="NOTION_TOKEN")
    
    # External APIs
    newsapi_key: Optional[str] = Field(default=None, alias="NEWSAPI_KEY")
    news_api_key: Optional[str] = Field(default=None, alias="NEWSAPI_KEY")  # alias for compatibility
    gnews_api_key: Optional[str] = Field(default=None, alias="GNEWS_API_KEY")
    brave_api_key: Optional[str] = Field(default=None, alias="BRAVE_API_KEY")
    guardian_api_key: Optional[str] = Field(default=None, alias="GUARDIAN_API_KEY")
    nyt_api_key: Optional[str] = Field(default=None, alias="NYT_API_KEY")
    coingecko_api_key: Optional[str] = Field(default=None, alias="COINGECKO_API_KEY")
    alpha_vantage_key: Optional[str] = Field(default=None, alias="ALPHA_VANTAGE_KEY")
    openweathermap_key: Optional[str] = Field(default=None, alias="OPENWEATHERMAP_KEY")
    
    # Services
    searxng_url: str = Field(default="http://localhost:8080", alias="SEARXNG_URL")
    playwright_service_url: str = Field(
        default="http://localhost:3001",
        alias="PLAYWRIGHT_SERVICE_URL"
    )
    n8n_webhook_url: Optional[str] = Field(default=None, alias="N8N_WEBHOOK_URL")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")
    
    @validator("cors_origins")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    @property
    def cors_origin_list(self) -> List[str]:
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins or ["http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Export settings instance
settings = get_settings()
