"""
Rate Limiting Middleware
Redis-based rate limiting for API endpoints
"""
from typing import Optional
from fastapi import Request, HTTPException, status
from app.utils.cache import cache
from app.utils.logging import get_logger
import time

logger = get_logger("rate_limiter")


class RateLimiter:
    """Redis-based rate limiter"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int  # seconds
    ) -> bool:
        """
        Check if request is allowed
        
        Args:
            key: Rate limit key (e.g., user_id, IP)
            limit: Max requests allowed
            window: Time window in seconds
            
        Returns:
            True if allowed, False if rate limited
        """
        try:
            current = await self.redis.incr(key)
            
            if current == 1:
                # First request in window, set expiration
                await self.redis.expire(key, window)
            
            return current <= limit
            
        except Exception as e:
            logger.error(f"Rate limiter error: {str(e)}")
            # Fail open - allow request if Redis is down
            return True
    
    async def check_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> None:
        """
        Check rate limit and raise exception if exceeded
        
        Args:
            key: Rate limit key
            limit: Max requests
            window: Time window in seconds
            
        Raises:
            HTTPException: If rate limited
        """
        allowed = await self.is_allowed(key, limit, window)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for key: {key}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {limit} requests per {window} seconds"
            )


# Global rate limiter
rate_limiter = RateLimiter(cache._redis if hasattr(cache, '_redis') else None)


async def rate_limit_middleware(
    request: Request,
    user_id: Optional[str] = None,
    limit: int = 60,
    window: int = 60
) -> None:
    """
    Rate limit middleware
    
    Args:
        request: FastAPI request
        user_id: User ID for rate limiting
        limit: Max requests
        window: Time window in seconds
    """
    if not user_id:
        # Use IP address as fallback
        user_id = request.client.host if request.client else "unknown"
    
    key = f"rate_limit:{user_id}:{int(time.time() // window)}"
    
    await rate_limiter.check_limit(key, limit, window)
