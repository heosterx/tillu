"""
Enhanced Cache Manager
Redis with connection pooling and health checks
"""
from typing import Any, Optional
from redis.asyncio import ConnectionPool, Redis
from app.utils.logging import get_logger
import json

logger = get_logger("cache")


class CacheManagerV2:
    """Redis cache with connection pooling"""
    
    def __init__(self, redis_url: str, max_connections: int = 20):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.pool: Optional[ConnectionPool] = None
        self.redis: Optional[Redis] = None
    
    async def connect(self):
        """Initialize connection pool"""
        try:
            self.pool = ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 1,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                },
                decode_responses=True
            )
            
            self.redis = Redis(connection_pool=self.pool)
            
            # Test connection
            await self.redis.ping()
            logger.info("Redis connected with connection pooling")
            
        except Exception as e:
            logger.error(f"Redis connection failed: {str(e)}")
            raise
    
    async def disconnect(self):
        """Close all connections"""
        if self.pool:
            await self.pool.disconnect()
            logger.info("Redis connection pool closed")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = await self.redis.get(key)
            
            if value:
                # Try to parse as JSON
                try:
                    return json.loads(value)
                except:
                    return value
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        try:
            # Convert to JSON if dict/list
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            if ttl:
                await self.redis.setex(key, ttl, value)
            else:
                await self.redis.set(key, value)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {str(e)}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter"""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache incr error: {str(e)}")
            return 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key"""
        try:
            await self.redis.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache expire error: {str(e)}")
            return False
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            
            return await self.redis.publish(channel, message)
            
        except Exception as e:
            logger.error(f"Cache publish error: {str(e)}")
            return 0
    
    async def subscribe(self, channel: str):
        """Subscribe to channel"""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error(f"Cache subscribe error: {str(e)}")
            return None
    
    async def is_healthy(self) -> bool:
        """Check if Redis is healthy"""
        try:
            await self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return False


# Global cache instance
cache_v2: Optional[CacheManagerV2] = None


async def init_cache(redis_url: str) -> CacheManagerV2:
    """Initialize global cache"""
    global cache_v2
    cache_v2 = CacheManagerV2(redis_url)
    await cache_v2.connect()
    return cache_v2


def get_cache() -> CacheManagerV2:
    """Get global cache instance"""
    if not cache_v2:
        raise RuntimeError("Cache not initialized. Call init_cache() first.")
    return cache_v2
