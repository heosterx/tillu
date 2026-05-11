"""
Token Budget Manager
Manages token usage across LLM providers
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.utils.cache_v2 import get_cache
from app.utils.logging import get_logger
from fastapi import HTTPException, status

logger = get_logger("token_budget")


class TokenBudgetManager:
    """Manage token usage across providers"""
    
    # Daily budgets (tokens/day)
    DAILY_BUDGETS = {
        "groq": 14400 * 60 * 24,  # tokens/min * min/hour * hours/day
        "cerebras": 200000,  # tokens/day
        "google": 1500 * 60 * 24,  # requests/day (approximate)
    }
    
    # Per-request limits
    REQUEST_LIMITS = {
        "groq": 2000,
        "cerebras": 4000,
        "google": 2000,
    }
    
    @classmethod
    async def allocate_tokens(
        cls,
        provider: str,
        estimated_tokens: int
    ) -> bool:
        """
        Check if tokens can be allocated from provider
        
        Args:
            provider: Provider name
            estimated_tokens: Estimated tokens needed
            
        Returns:
            True if allocation successful, False otherwise
        """
        
        if provider not in cls.DAILY_BUDGETS:
            logger.warning(f"Unknown provider: {provider}")
            return False
        
        # Check request limit
        if estimated_tokens > cls.REQUEST_LIMITS.get(provider, 2000):
            logger.warning(
                f"Request exceeds limit for {provider}: "
                f"{estimated_tokens} > {cls.REQUEST_LIMITS[provider]}"
            )
            return False
        
        try:
            cache = get_cache()
            
            # Get today's usage
            today = datetime.utcnow().date().isoformat()
            usage_key = f"token_usage:{provider}:{today}"
            
            used = await cache.get(usage_key)
            used = int(used or 0)
            
            budget = cls.DAILY_BUDGETS[provider]
            
            if used + estimated_tokens < budget:
                # Allocate tokens
                await cache.incr(usage_key, estimated_tokens)
                
                # Set expiration to 24 hours
                await cache.expire(usage_key, 86400)
                
                logger.info(
                    f"Allocated {estimated_tokens} tokens from {provider} "
                    f"({used + estimated_tokens}/{budget})"
                )
                
                return True
            else:
                logger.warning(
                    f"Token budget exceeded for {provider}: "
                    f"{used + estimated_tokens} > {budget}"
                )
                return False
                
        except Exception as e:
            logger.error(f"Token allocation error: {str(e)}")
            # Fail open - allow request if cache is down
            return True
    
    @classmethod
    async def get_usage(cls, provider: str) -> Dict[str, int]:
        """Get current usage for provider"""
        
        try:
            cache = get_cache()
            
            today = datetime.utcnow().date().isoformat()
            usage_key = f"token_usage:{provider}:{today}"
            
            used = await cache.get(usage_key)
            used = int(used or 0)
            
            budget = cls.DAILY_BUDGETS.get(provider, 0)
            
            return {
                "provider": provider,
                "used": used,
                "budget": budget,
                "remaining": max(0, budget - used),
                "percentage": (used / budget * 100) if budget > 0 else 0,
                "date": today
            }
            
        except Exception as e:
            logger.error(f"Error getting usage: {str(e)}")
            return {
                "provider": provider,
                "error": str(e)
            }
    
    @classmethod
    async def get_all_usage(cls) -> Dict[str, Dict]:
        """Get usage for all providers"""
        
        usage = {}
        for provider in cls.DAILY_BUDGETS.keys():
            usage[provider] = await cls.get_usage(provider)
        
        return usage
    
    @classmethod
    async def select_provider_with_budget(
        cls,
        providers: list,
        estimated_tokens: int
    ) -> Optional[str]:
        """
        Select provider with available budget
        
        Args:
            providers: List of provider names (in priority order)
            estimated_tokens: Estimated tokens needed
            
        Returns:
            Selected provider name or None if no budget available
        """
        
        for provider in providers:
            if await cls.allocate_tokens(provider, estimated_tokens):
                return provider
        
        logger.error(f"No provider has budget for {estimated_tokens} tokens")
        return None
    
    @classmethod
    async def reset_daily_budget(cls, provider: str) -> bool:
        """Reset daily budget for provider (admin only)"""
        
        try:
            cache = get_cache()
            
            today = datetime.utcnow().date().isoformat()
            usage_key = f"token_usage:{provider}:{today}"
            
            await cache.delete(usage_key)
            
            logger.info(f"Reset daily budget for {provider}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting budget: {str(e)}")
            return False
