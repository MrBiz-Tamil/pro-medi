"""
Redis Caching Utility for MediHub API
Provides caching for doctor profiles, availability, and other frequently accessed data.
"""

import redis
import json
import os
from typing import Optional, Any, List, TypeVar, Callable
from functools import wraps
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Type variable for generic caching
T = TypeVar('T')

# Redis connection settings
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"

# Cache TTL settings (in seconds)
class CacheTTL:
    DOCTOR_PROFILE = 300  # 5 minutes
    DOCTOR_LIST = 180  # 3 minutes
    DOCTOR_AVAILABILITY = 120  # 2 minutes
    ONLINE_DOCTORS = 60  # 1 minute (changes frequently)
    SPECIALIZATIONS = 3600  # 1 hour (rarely changes)
    SEARCH_RESULTS = 300  # 5 minutes
    USER_SESSION = 1800  # 30 minutes


# Cache key prefixes
class CacheKeys:
    DOCTOR_PROFILE = "doctor:profile:{doctor_id}"
    DOCTOR_LIST = "doctors:list:verified"
    DOCTOR_AVAILABILITY = "doctor:availability:{doctor_id}"
    ONLINE_DOCTORS = "doctors:online"
    SPECIALIZATIONS = "specializations:list"
    DOCTOR_SEARCH = "doctors:search:{query}"
    DOCTOR_BY_SPECIALIZATION = "doctors:spec:{specialization}"


class RedisCache:
    """Redis cache manager with connection pooling and error handling"""
    
    _instance: Optional['RedisCache'] = None
    _redis_client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._redis_client is None and CACHE_ENABLED:
            try:
                self._redis_client = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                self._redis_client.ping()
                logger.info("Redis cache connected successfully")
            except redis.ConnectionError as e:
                logger.warning(f"Redis connection failed: {e}. Caching disabled.")
                self._redis_client = None
            except Exception as e:
                logger.warning(f"Redis initialization error: {e}. Caching disabled.")
                self._redis_client = None
    
    @property
    def client(self) -> Optional[redis.Redis]:
        return self._redis_client
    
    @property
    def is_available(self) -> bool:
        if not CACHE_ENABLED or self._redis_client is None:
            return False
        try:
            self._redis_client.ping()
            return True
        except:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.is_available:
            return None
        try:
            value = self._redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set value in cache with TTL"""
        if not self.is_available:
            return False
        try:
            serialized = json.dumps(value, default=str)
            self._redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.is_available:
            return False
        try:
            self._redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.is_available:
            return 0
        try:
            keys = self._redis_client.keys(pattern)
            if keys:
                return self._redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    def get_many(self, keys: List[str]) -> dict:
        """Get multiple values from cache"""
        if not self.is_available or not keys:
            return {}
        try:
            values = self._redis_client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value:
                    result[key] = json.loads(value)
            return result
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        if not self.is_available:
            return None
        try:
            return self._redis_client.incr(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None
    
    def add_to_set(self, key: str, *values, ttl: int = None) -> bool:
        """Add values to a set"""
        if not self.is_available:
            return False
        try:
            self._redis_client.sadd(key, *values)
            if ttl:
                self._redis_client.expire(key, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache add_to_set error for key {key}: {e}")
            return False
    
    def get_set_members(self, key: str) -> set:
        """Get all members of a set"""
        if not self.is_available:
            return set()
        try:
            return self._redis_client.smembers(key)
        except Exception as e:
            logger.error(f"Cache get_set_members error for key {key}: {e}")
            return set()


# Singleton instance
cache = RedisCache()


# Doctor-specific cache functions
class DoctorCache:
    """Doctor-specific caching operations"""
    
    @staticmethod
    def get_profile(doctor_id: int) -> Optional[dict]:
        """Get cached doctor profile"""
        key = CacheKeys.DOCTOR_PROFILE.format(doctor_id=doctor_id)
        return cache.get(key)
    
    @staticmethod
    def set_profile(doctor_id: int, profile_data: dict) -> bool:
        """Cache doctor profile"""
        key = CacheKeys.DOCTOR_PROFILE.format(doctor_id=doctor_id)
        return cache.set(key, profile_data, CacheTTL.DOCTOR_PROFILE)
    
    @staticmethod
    def invalidate_profile(doctor_id: int) -> bool:
        """Invalidate cached doctor profile"""
        key = CacheKeys.DOCTOR_PROFILE.format(doctor_id=doctor_id)
        return cache.delete(key)
    
    @staticmethod
    def get_availability(doctor_id: int) -> Optional[list]:
        """Get cached doctor availability"""
        key = CacheKeys.DOCTOR_AVAILABILITY.format(doctor_id=doctor_id)
        return cache.get(key)
    
    @staticmethod
    def set_availability(doctor_id: int, availability_data: list) -> bool:
        """Cache doctor availability"""
        key = CacheKeys.DOCTOR_AVAILABILITY.format(doctor_id=doctor_id)
        return cache.set(key, availability_data, CacheTTL.DOCTOR_AVAILABILITY)
    
    @staticmethod
    def invalidate_availability(doctor_id: int) -> bool:
        """Invalidate cached doctor availability"""
        key = CacheKeys.DOCTOR_AVAILABILITY.format(doctor_id=doctor_id)
        return cache.delete(key)
    
    @staticmethod
    def get_verified_list() -> Optional[list]:
        """Get cached list of verified doctors"""
        return cache.get(CacheKeys.DOCTOR_LIST)
    
    @staticmethod
    def set_verified_list(doctors_data: list) -> bool:
        """Cache list of verified doctors"""
        return cache.set(CacheKeys.DOCTOR_LIST, doctors_data, CacheTTL.DOCTOR_LIST)
    
    @staticmethod
    def invalidate_verified_list() -> bool:
        """Invalidate cached verified doctors list"""
        return cache.delete(CacheKeys.DOCTOR_LIST)
    
    @staticmethod
    def get_online_doctors() -> Optional[list]:
        """Get cached list of online doctors"""
        return cache.get(CacheKeys.ONLINE_DOCTORS)
    
    @staticmethod
    def set_online_doctors(doctors_data: list) -> bool:
        """Cache list of online doctors"""
        return cache.set(CacheKeys.ONLINE_DOCTORS, doctors_data, CacheTTL.ONLINE_DOCTORS)
    
    @staticmethod
    def invalidate_online_doctors() -> bool:
        """Invalidate online doctors cache"""
        return cache.delete(CacheKeys.ONLINE_DOCTORS)
    
    @staticmethod
    def invalidate_all_for_doctor(doctor_id: int) -> None:
        """Invalidate all cache entries for a specific doctor"""
        DoctorCache.invalidate_profile(doctor_id)
        DoctorCache.invalidate_availability(doctor_id)
        DoctorCache.invalidate_verified_list()
        DoctorCache.invalidate_online_doctors()


def cached(key_template: str, ttl: int = 300):
    """
    Decorator for caching function results.
    
    Usage:
        @cached("user:{user_id}", ttl=600)
        def get_user(user_id: int):
            return db.get_user(user_id)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Build cache key from template and arguments
            key = key_template.format(**kwargs, **(dict(zip(func.__code__.co_varnames, args))))
            
            # Try to get from cache
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            if result is not None:
                cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator


def invalidate_cache(*keys: str):
    """
    Decorator to invalidate cache keys after function execution.
    
    Usage:
        @invalidate_cache("user:{user_id}", "users:list")
        def update_user(user_id: int, data: dict):
            return db.update_user(user_id, data)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            result = func(*args, **kwargs)
            
            # Invalidate specified cache keys
            for key_template in keys:
                try:
                    key = key_template.format(**kwargs, **(dict(zip(func.__code__.co_varnames, args))))
                    cache.delete(key)
                except KeyError:
                    # Key template doesn't match function arguments
                    cache.delete(key_template)
            
            return result
        return wrapper
    return decorator
