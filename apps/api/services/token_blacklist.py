"""
Token Blacklist Service
Manages invalidated tokens to support secure logout functionality.

In production, this should use Redis for distributed systems.
Currently uses in-memory storage for development/single-instance deployments.
"""

import os
import time
import logging
from typing import Set, Optional
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

# Try to import Redis for production use
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. Using in-memory token blacklist (not suitable for production).")


class TokenBlacklist:
    """
    Token blacklist to invalidate JWT tokens before expiry.
    
    Features:
    - Automatic cleanup of expired entries
    - Redis support for production (distributed systems)
    - In-memory fallback for development
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        """Singleton pattern for global access."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the blacklist storage."""
        self._redis_client: Optional[redis.Redis] = None
        self._memory_blacklist: Set[str] = set()
        self._memory_expiry: dict = {}  # token -> expiry_timestamp
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # Clean up every 5 minutes
        
        # Try to connect to Redis
        redis_url = os.getenv("REDIS_URL")
        if redis_url and REDIS_AVAILABLE:
            try:
                self._redis_client = redis.from_url(redis_url, decode_responses=True)
                self._redis_client.ping()
                logger.info("Token blacklist using Redis")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory blacklist.")
                self._redis_client = None
        else:
            logger.info("Token blacklist using in-memory storage (development mode)")
    
    def add(self, token: str, token_jti: Optional[str] = None, expires_in_seconds: int = 3600) -> bool:
        """
        Add a token to the blacklist.
        
        Args:
            token: The JWT token string (or just the JTI if available)
            token_jti: The JWT ID (jti) claim if available
            expires_in_seconds: How long to keep the token in blacklist
        
        Returns:
            True if successfully added
        """
        # Use JTI if available for smaller storage, otherwise hash the token
        key = token_jti if token_jti else self._hash_token(token)
        
        try:
            if self._redis_client:
                # Redis: use SET with expiry
                self._redis_client.setex(
                    f"blacklist:{key}",
                    expires_in_seconds,
                    "1"
                )
            else:
                # In-memory: store with expiry timestamp
                expiry = time.time() + expires_in_seconds
                self._memory_blacklist.add(key)
                self._memory_expiry[key] = expiry
                self._cleanup_expired()
            
            return True
        except Exception as e:
            logger.error(f"Failed to add token to blacklist: {e}")
            return False
    
    def is_blacklisted(self, token: str, token_jti: Optional[str] = None) -> bool:
        """
        Check if a token is blacklisted.
        
        Args:
            token: The JWT token string
            token_jti: The JWT ID (jti) claim if available
        
        Returns:
            True if token is blacklisted
        """
        key = token_jti if token_jti else self._hash_token(token)
        
        try:
            if self._redis_client:
                return self._redis_client.exists(f"blacklist:{key}") > 0
            else:
                self._cleanup_expired()
                return key in self._memory_blacklist
        except Exception as e:
            logger.error(f"Failed to check blacklist: {e}")
            # Fail safe: if we can't check, assume not blacklisted
            return False
    
    def remove(self, token: str, token_jti: Optional[str] = None) -> bool:
        """
        Remove a token from the blacklist (rarely needed).
        
        Args:
            token: The JWT token string
            token_jti: The JWT ID (jti) claim if available
        
        Returns:
            True if successfully removed
        """
        key = token_jti if token_jti else self._hash_token(token)
        
        try:
            if self._redis_client:
                self._redis_client.delete(f"blacklist:{key}")
            else:
                self._memory_blacklist.discard(key)
                self._memory_expiry.pop(key, None)
            return True
        except Exception as e:
            logger.error(f"Failed to remove token from blacklist: {e}")
            return False
    
    def _hash_token(self, token: str) -> str:
        """Hash token for storage (don't store full tokens)."""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()[:32]
    
    def _cleanup_expired(self):
        """Remove expired entries from in-memory storage."""
        if self._redis_client:
            return  # Redis handles expiry automatically
        
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        expired = [k for k, v in self._memory_expiry.items() if v < now]
        for key in expired:
            self._memory_blacklist.discard(key)
            self._memory_expiry.pop(key, None)
        
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired blacklist entries")
    
    def clear(self):
        """Clear all blacklisted tokens (for testing)."""
        if self._redis_client:
            # Clear all blacklist keys
            keys = self._redis_client.keys("blacklist:*")
            if keys:
                self._redis_client.delete(*keys)
        else:
            self._memory_blacklist.clear()
            self._memory_expiry.clear()


# Global instance
token_blacklist = TokenBlacklist()


def blacklist_token(token: str, token_jti: Optional[str] = None, expires_in_seconds: int = 3600) -> bool:
    """Convenience function to blacklist a token."""
    return token_blacklist.add(token, token_jti, expires_in_seconds)


def is_token_blacklisted(token: str, token_jti: Optional[str] = None) -> bool:
    """Convenience function to check if token is blacklisted."""
    return token_blacklist.is_blacklisted(token, token_jti)
