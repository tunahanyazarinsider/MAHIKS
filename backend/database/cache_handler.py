import redis
import json
import hashlib
import pickle
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class CacheHandler:
    """Redis-based caching for MAHIKS-TR queries and embeddings."""

    def __init__(self, host: str = "redis", port: int = 6379, db: int = 0):
        """
        Initialize Redis connection.

        Args:
            host: Redis host (use 'redis' for Docker, 'localhost' for local)
            port: Redis port (default 6379)
            db: Redis database number (default 0)
        """
        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=False,  # We'll handle encoding
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis.ping()
            logger.info(f"✓ Connected to Redis at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    def _generate_key(self, prefix: str, *args) -> str:
        """
        Generate cache key from prefix and arguments.

        Args:
            prefix: Key prefix (e.g., 'query', 'embedding')
            *args: Values to hash

        Returns:
            Cache key string
        """
        # Combine all args and hash
        combined = "|".join(str(arg) for arg in args)
        hash_value = hashlib.sha256(combined.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_value}"

    def get_query_cache(self, question: str) -> Optional[dict]:
        """
        Get cached query response.

        Args:
            question: User question

        Returns:
            Cached response dict or None
        """
        if not self.redis:
            return None

        try:
            # Normalize question (lowercase, strip whitespace)
            normalized = question.lower().strip()
            key = self._generate_key("query", normalized)

            cached = self.redis.get(key)
            if cached:
                logger.info(f"✓ Cache HIT for query: {question[:50]}...")
                return json.loads(cached)

            logger.debug(f"Cache MISS for query: {question[:50]}...")
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set_query_cache(self, question: str, response: dict, ttl: int = 3600):
        """
        Cache query response.

        Args:
            question: User question
            response: Query response dict
            ttl: Time to live in seconds (default 1 hour)
        """
        if not self.redis:
            return

        try:
            normalized = question.lower().strip()
            key = self._generate_key("query", normalized)

            # Store as JSON with TTL
            self.redis.setex(
                key,
                ttl,
                json.dumps(response, ensure_ascii=False)
            )
            logger.debug(f"✓ Cached query response (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def get_embedding_cache(self, text: str) -> Optional[Any]:
        """
        Get cached embedding vector.

        Args:
            text: Text that was embedded

        Returns:
            Numpy array or None
        """
        if not self.redis:
            return None

        try:
            normalized = text.lower().strip()
            key = self._generate_key("embedding", normalized)

            cached = self.redis.get(key)
            if cached:
                logger.debug(f"✓ Cache HIT for embedding")
                return pickle.loads(cached)

            return None
        except Exception as e:
            logger.error(f"Embedding cache get error: {e}")
            return None

    def set_embedding_cache(self, text: str, embedding: Any, ttl: int = 86400):
        """
        Cache embedding vector.

        Args:
            text: Text that was embedded
            embedding: Numpy array or list
            ttl: Time to live in seconds (default 24 hours)
        """
        if not self.redis:
            return

        try:
            normalized = text.lower().strip()
            key = self._generate_key("embedding", normalized)

            # Pickle numpy array
            self.redis.setex(key, ttl, pickle.dumps(embedding))
            logger.debug(f"✓ Cached embedding (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Embedding cache set error: {e}")

    def invalidate_all(self):
        """Clear all cache entries."""
        if not self.redis:
            return

        try:
            self.redis.flushdb()
            logger.info("✓ All cache cleared")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    def invalidate_queries(self):
        """Clear only query caches (keep embeddings)."""
        if not self.redis:
            return

        try:
            # Find all query keys
            for key in self.redis.scan_iter("query:*"):
                self.redis.delete(key)
            logger.info("✓ Query cache cleared")
        except Exception as e:
            logger.error(f"Query cache clear error: {e}")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.redis:
            return {"status": "disconnected"}

        try:
            info = self.redis.info()
            return {
                "status": "connected",
                "used_memory_human": info.get("used_memory_human"),
                "total_keys": self.redis.dbsize(),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {"status": "error", "message": str(e)}

    def _calculate_hit_rate(self, hits: int, misses: int) -> str:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return "0%"
        return f"{(hits / total * 100):.1f}%"


# Global instance
cache_handler = None


def get_cache_handler() -> Optional[CacheHandler]:
    """Get global cache handler instance."""
    return cache_handler


def init_cache_handler(host: str = "redis", port: int = 6379):
    """Initialize global cache handler."""
    global cache_handler
    cache_handler = CacheHandler(host=host, port=port)
    return cache_handler