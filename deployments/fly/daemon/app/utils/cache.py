"""
Cache manager for Redis operations
"""
import json
from typing import Any, Optional, List
from datetime import timedelta
import redis.asyncio as redis
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("cache")


class CacheManager:
    """Redis cache manager with async support"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._redis = None
        return cls._instance
    
    async def connect(self):
        """Initialize Redis connection"""
        if self._redis is None:
            try:
                self._redis = await redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self._redis.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.error("Failed to connect to Redis", error=str(e))
                raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Cache get error", key=key, error=str(e))
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL"""
        try:
            serialized = json.dumps(value, default=str)
            if ttl:
                await self._redis.setex(key, ttl, serialized)
            else:
                await self._redis.set(key, serialized)
            return True
        except Exception as e:
            logger.error("Cache set error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error("Cache delete error", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.error("Cache exists error", key=key, error=str(e))
            return False
    
    async def ttl(self, key: str) -> int:
        """Get TTL of key"""
        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.error("Cache ttl error", key=key, error=str(e))
            return -1
    
    async def publish(self, channel: str, message: Any) -> bool:
        """Publish message to Redis channel"""
        try:
            serialized = json.dumps(message, default=str) if not isinstance(message, str) else message
            await self._redis.publish(channel, serialized)
            return True
        except Exception as e:
            logger.error("Cache publish error", channel=channel, error=str(e))
            return False
    
    async def subscribe(self, channel: str):
        """Subscribe to Redis channel"""
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error("Cache subscribe error", channel=channel, error=str(e))
            return None
    
    async def lpush(self, key: str, value: Any) -> bool:
        """Push value to list head"""
        try:
            serialized = json.dumps(value, default=str)
            await self._redis.lpush(key, serialized)
            return True
        except Exception as e:
            logger.error("Cache lpush error", key=key, error=str(e))
            return False
    
    async def rpop(self, key: str) -> Optional[Any]:
        """Pop value from list tail"""
        try:
            value = await self._redis.rpop(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Cache rpop error", key=key, error=str(e))
            return None
    
    async def llen(self, key: str) -> int:
        """Get list length"""
        try:
            return await self._redis.llen(key)
        except Exception as e:
            logger.error("Cache llen error", key=key, error=str(e))
            return 0
    
    async def zadd(self, key: str, score: float, member: Any) -> bool:
        """Add member to sorted set"""
        try:
            serialized = json.dumps(member, default=str) if not isinstance(member, str) else member
            await self._redis.zadd(key, {serialized: score})
            return True
        except Exception as e:
            logger.error("Cache zadd error", key=key, error=str(e))
            return False
    
    async def zrange(self, key: str, start: int, end: int) -> List[Any]:
        """Get range from sorted set"""
        try:
            values = await self._redis.zrange(key, start, end)
            return [json.loads(v) for v in values]
        except Exception as e:
            logger.error("Cache zrange error", key=key, error=str(e))
            return []


# Global cache instance
cache = CacheManager()
