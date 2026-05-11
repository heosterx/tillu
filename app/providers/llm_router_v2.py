"""
Enhanced LLM Router with Fallback and Circuit Breaker
Intelligent provider selection with automatic fallback
"""
import time
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.config import settings
from app.utils.logging import get_logger
from fastapi import HTTPException, status
import httpx

logger = get_logger("llm_router")


class CircuitBreaker:
    """Circuit breaker for provider failures"""
    
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def record_success(self):
        """Record successful call"""
        self.failures = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed call"""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failures} failures")
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == "open":
            # Check if reset timeout passed
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "half_open"
                self.failures = 0
                logger.info("Circuit breaker half-open, attempting recovery")
                return False
            return True
        return False


class LLMRouter:
    """Intelligent LLM routing with fallback and circuit breaker"""
    
    def __init__(self):
        self.providers = [
            {
                "name": "groq",
                "priority": 1,
                "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"],
                "api_url": "https://api.groq.com/openai/v1/chat/completions",
                "key_env": "GROQ_API_KEY"
            },
            {
                "name": "cerebras",
                "priority": 2,
                "models": ["llama-3.3-70b"],
                "api_url": "https://api.cerebras.ai/v1/chat/completions",
                "key_env": "CEREBRAS_API_KEY"
            },
            {
                "name": "google",
                "priority": 3,
                "models": ["gemini-1.5-flash"],
                "api_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                "key_env": "GOOGLE_API_KEY"
            },
        ]
        
        # Initialize circuit breakers
        self.circuit_breakers = {p["name"]: CircuitBreaker() for p in self.providers}
        
        # Token tracking
        self.token_usage = {}
    
    async def invoke_with_fallback(
        self,
        messages: List[Dict[str, str]],
        task: str = "general",
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Invoke LLM with automatic fallback
        
        Args:
            messages: OpenAI-style message list
            task: Task type for provider ranking
            max_tokens: Max tokens in response
            temperature: Sampling temperature
            
        Returns:
            Response with provider info
            
        Raises:
            HTTPException: If all providers fail
        """
        
        # Get provider ranking for this task
        providers = self._rank_providers(task)
        
        last_error = None
        for provider_config in providers:
            provider_name = provider_config["name"]
            
            # Check circuit breaker
            if self.circuit_breakers[provider_name].is_open():
                logger.warning(f"Circuit breaker open for {provider_name}, skipping")
                continue
            
            try:
                logger.info(f"Attempting LLM call with {provider_name}")
                
                result = await self._call_provider(
                    provider_config,
                    messages,
                    max_tokens,
                    temperature
                )
                
                # Success - reset circuit breaker
                self.circuit_breakers[provider_name].record_success()
                
                logger.info(f"LLM call successful with {provider_name}")
                
                return {
                    "content": result,
                    "provider": provider_name,
                    "success": True,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {str(e)}")
                self.circuit_breakers[provider_name].record_failure()
                last_error = e
                continue
        
        # All providers failed
        logger.error(f"All LLM providers failed. Last error: {last_error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"All LLM providers unavailable: {str(last_error)}"
        )
    
    def _rank_providers(self, task: str) -> List[Dict[str, Any]]:
        """Rank providers by task type"""
        
        task_preferences = {
            "analysis": ["cerebras", "groq", "google"],
            "research": ["cerebras", "groq", "google"],
            "conversational": ["groq", "cerebras", "google"],
            "react_agent": ["google", "groq", "cerebras"],
            "general": ["groq", "cerebras", "google"],
        }
        
        preferred_names = task_preferences.get(task, ["groq", "cerebras", "google"])
        
        # Sort providers by preference
        ranked = sorted(
            self.providers,
            key=lambda p: preferred_names.index(p["name"]) if p["name"] in preferred_names else 999
        )
        
        return ranked
    
    async def _call_provider(
        self,
        provider_config: Dict[str, Any],
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call specific LLM provider"""
        
        provider_name = provider_config["name"]
        
        # Get API key
        api_key = getattr(settings, provider_config["key_env"].lower(), None)
        if not api_key:
            raise ValueError(f"API key not configured for {provider_name}")
        
        # Provider-specific implementations
        if provider_name == "groq":
            return await self._call_groq(api_key, messages, max_tokens, temperature)
        elif provider_name == "cerebras":
            return await self._call_cerebras(api_key, messages, max_tokens, temperature)
        elif provider_name == "google":
            return await self._call_google(api_key, messages, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
    
    async def _call_groq(
        self,
        api_key: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call Groq API"""
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data["choices"][0]["message"]["content"]
    
    async def _call_cerebras(
        self,
        api_key: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call Cerebras API"""
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.cerebras.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b",
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data["choices"][0]["message"]["content"]
    
    async def _call_google(
        self,
        api_key: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Call Google Gemini API"""
        
        # Convert OpenAI format to Google format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": contents,
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": temperature
                    }
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            return data["candidates"][0]["content"]["parts"][0]["text"]


# Global router instance
llm_router = LLMRouter()
