import redis
from functools import wraps
from typing import Optional, Any
import json
from app.config import settings

# Redis connection pool
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True
)

def get_redis():
    """Return Redis connection."""
    try:
        redis_client.ping()
        return redis_client
    except redis.ConnectionError:
        raise ConnectionError("Could not connect to Redis server")

def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    return ":".join(key_parts)

def cache(ttl: int = settings.CACHE_TTL):
    """Cache decorator for functions.
    
    Args:
        ttl (int): Time to live in seconds. Defaults to CACHE_TTL from settings.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)
            
            # Get fresh data
            result = await func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                redis_client.setex(key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

def clear_cache(pattern: str = "*"):
    """Clear cache entries matching pattern."""
    try:
        for key in redis_client.scan_iter(pattern):
            redis_client.delete(key)
    except redis.ConnectionError:
        raise ConnectionError("Could not connect to Redis server")

def get_cached(key: str) -> Optional[Any]:
    """Get value from cache."""
    try:
        value = redis_client.get(key)
        return json.loads(value) if value else None
    except redis.ConnectionError:
        raise ConnectionError("Could not connect to Redis server")

def set_cached(key: str, value: Any, ttl: int = settings.CACHE_TTL):
    """Set value in cache."""
    try:
        redis_client.setex(key, ttl, json.dumps(value))
    except redis.ConnectionError:
        raise ConnectionError("Could not connect to Redis server") 