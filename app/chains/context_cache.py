"""
Context Caching Layer
Smart caching with TTL strategies for context assembly
"""
from typing import Dict, Any, Optional
from app.utils.cache_v2 import get_cache
from app.utils.logging import get_logger
import hashlib

logger = get_logger("context_cache")


class ContextCache:
    """Smart context caching with TTL strategies"""
    
    # Cache strategies: {tier: {ttl, key_pattern}}
    CACHE_STRATEGIES = {
        "identity": {
            "ttl": 3600,  # 1 hour
            "key": "ctx:identity:{user_id}"
        },
        "emotional": {
            "ttl": 1800,  # 30 minutes
            "key": "ctx:emotional:{user_id}"
        },
        "world_state": {
            "ttl": 600,  # 10 minutes
            "key": "ctx:world_state:{user_id}"
        },
        "semantic": {
            "ttl": 300,  # 5 minutes
            "key": "ctx:semantic:{user_id}:{query_hash}"
        },
        "situational": {
            "ttl": 900,  # 15 minutes
            "key": "ctx:situational:{user_id}"
        },
    }
    
    @classmethod
    async def get_or_assemble(
        cls,
        tier: str,
        user_id: str,
        assemble_func,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Get from cache or assemble tier
        
        Args:
            tier: Context tier name
            user_id: User ID
            assemble_func: Async function to assemble tier
            **kwargs: Additional parameters for key generation
            
        Returns:
            Cached or assembled context tier
        """
        
        strategy = cls.CACHE_STRATEGIES.get(tier)
        if not strategy:
            # No caching for this tier
            return await assemble_func(user_id, **kwargs)
        
        # Generate cache key
        cache_key = strategy["key"].format(user_id=user_id, **kwargs)
        
        try:
            cache = get_cache()
            
            # Try to get from cache
            cached = await cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {tier}")
                return cached
            
        except Exception as e:
            logger.warning(f"Cache get failed: {str(e)}")
        
        # Assemble tier
        logger.debug(f"Assembling {tier} for user {user_id}")
        data = await assemble_func(user_id, **kwargs)
        
        # Store in cache
        try:
            cache = get_cache()
            await cache.set(cache_key, data, ttl=strategy["ttl"])
            logger.debug(f"Cached {tier} for {strategy['ttl']}s")
        except Exception as e:
            logger.warning(f"Cache set failed: {str(e)}")
        
        return data
    
    @classmethod
    async def invalidate(cls, tier: str, user_id: str, **kwargs) -> bool:
        """
        Invalidate cache for a tier
        
        Args:
            tier: Context tier name
            user_id: User ID
            **kwargs: Additional parameters for key generation
            
        Returns:
            True if invalidated, False otherwise
        """
        
        strategy = cls.CACHE_STRATEGIES.get(tier)
        if not strategy:
            return False
        
        cache_key = strategy["key"].format(user_id=user_id, **kwargs)
        
        try:
            cache = get_cache()
            await cache.delete(cache_key)
            logger.info(f"Invalidated cache for {tier}")
            return True
        except Exception as e:
            logger.error(f"Cache invalidation failed: {str(e)}")
            return False
    
    @classmethod
    async def invalidate_user(cls, user_id: str) -> int:
        """
        Invalidate all cache for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Number of keys invalidated
        """
        
        count = 0
        try:
            cache = get_cache()
            
            for tier in cls.CACHE_STRATEGIES.keys():
                if await cls.invalidate(tier, user_id):
                    count += 1
            
            logger.info(f"Invalidated {count} cache entries for user {user_id}")
            return count
            
        except Exception as e:
            logger.error(f"User cache invalidation failed: {str(e)}")
            return count
    
    @classmethod
    def _hash_query(cls, query: str) -> str:
        """Hash query for cache key"""
        return hashlib.md5(query.encode()).hexdigest()[:8]
