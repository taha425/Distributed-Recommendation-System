"""
redis_cache.py
--------------
Simulates Redis caching behavior using an in-memory LRU cache.

In a production system, this would be replaced with:
  import redis
  r = redis.Redis(host='localhost', port=6379)
  r.setex(key, ttl, json.dumps(value))

The simulation mimics:
  - GET / SET / DEL operations
  - TTL (time-to-live) expiry
  - LRU eviction policy
  - HSET / HGET for hash structures
  - ZADD / ZRANGE for sorted sets (trending products)
"""

import time
import json
import threading
from collections import OrderedDict
from typing import Any, Optional, List, Tuple


class RedisCache:
    """
    In-memory Redis simulation with LRU eviction and TTL support.

    Architecture mirrors Redis:
      - Key-value store (STRING type)
      - Hash store (HASH type)
      - Sorted set store (ZSET type)
      - LRU eviction when max_size reached
    """

    def __init__(self, max_size: int = 10_000, default_ttl: int = 3600):
        self._max_size    = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict = OrderedDict()   # key → (value, expire_at)
        self._hstore: dict       = {}               # key → {field: value}
        self._zsets:  dict       = {}               # key → {member: score}
        self._lock    = threading.Lock()

        # Metrics (mirrors Redis INFO)
        self._hits   = 0
        self._misses = 0
        self._total_set = 0
        self._evictions = 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_expired(self, expire_at: Optional[float]) -> bool:
        if expire_at is None:
            return False
        return time.time() > expire_at

    def _evict_lru(self):
        """Evict least-recently-used items when cache is full."""
        while len(self._store) >= self._max_size:
            self._store.popitem(last=False)
            self._evictions += 1

    def _touch(self, key: str):
        """Move key to end of OrderedDict (most recently used)."""
        if key in self._store:
            self._store.move_to_end(key)

    # ── STRING operations ─────────────────────────────────────────────────────

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """SET key value [EX ttl]"""
        with self._lock:
            expire_at = time.time() + (ttl or self._default_ttl)
            self._evict_lru()
            self._store[key] = (json.dumps(value), expire_at)
            self._store.move_to_end(key)
            self._total_set += 1
            return True

    def get(self, key: str) -> Optional[Any]:
        """GET key"""
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            value, expire_at = self._store[key]
            if self._is_expired(expire_at):
                del self._store[key]
                self._misses += 1
                return None
            self._touch(key)
            self._hits += 1
            return json.loads(value)

    def delete(self, *keys: str) -> int:
        """DEL key [key ...]"""
        with self._lock:
            count = 0
            for key in keys:
                if key in self._store:
                    del self._store[key]
                    count += 1
            return count

    def exists(self, key: str) -> bool:
        """EXISTS key"""
        return self.get(key) is not None

    def ttl(self, key: str) -> int:
        """TTL key — returns remaining TTL in seconds, -2 if not found."""
        with self._lock:
            if key not in self._store:
                return -2
            _, expire_at = self._store[key]
            if expire_at is None:
                return -1
            remaining = expire_at - time.time()
            return max(0, int(remaining))

    def flush(self):
        """FLUSHALL"""
        with self._lock:
            self._store.clear()
            self._hstore.clear()
            self._zsets.clear()

    # ── HASH operations ───────────────────────────────────────────────────────

    def hset(self, key: str, field: str, value: Any) -> int:
        """HSET key field value"""
        with self._lock:
            if key not in self._hstore:
                self._hstore[key] = {}
            is_new = field not in self._hstore[key]
            self._hstore[key][field] = json.dumps(value)
            return 1 if is_new else 0

    def hget(self, key: str, field: str) -> Optional[Any]:
        """HGET key field"""
        with self._lock:
            val = self._hstore.get(key, {}).get(field)
            if val is None:
                return None
            return json.loads(val)

    def hgetall(self, key: str) -> dict:
        """HGETALL key"""
        with self._lock:
            return {
                f: json.loads(v)
                for f, v in self._hstore.get(key, {}).items()
            }

    # ── SORTED SET operations ─────────────────────────────────────────────────

    def zadd(self, key: str, members: dict):
        """ZADD key score member [score member ...]  (members = {member: score})"""
        with self._lock:
            if key not in self._zsets:
                self._zsets[key] = {}
            self._zsets[key].update(members)

    def zrange(self, key: str, start: int = 0, stop: int = -1,
               reverse: bool = False) -> List[Tuple[str, float]]:
        """ZRANGE key start stop [WITHSCORES] [REV]"""
        with self._lock:
            if key not in self._zsets:
                return []
            items = sorted(self._zsets[key].items(), key=lambda x: x[1], reverse=reverse)
            if stop == -1:
                stop = len(items)
            return items[start:stop + 1]

    def zincrby(self, key: str, amount: float, member: str):
        """ZINCRBY key increment member"""
        with self._lock:
            if key not in self._zsets:
                self._zsets[key] = {}
            self._zsets[key][member] = self._zsets[key].get(member, 0) + amount

    # ── Cache-aside helpers ───────────────────────────────────────────────────

    def get_recommendations(self, user_id: int) -> Optional[List]:
        """Cache-aside GET for user recommendations."""
        return self.get(f"recs:{user_id}")

    def set_recommendations(self, user_id: int, recs: List, ttl: int = 1800):
        """Cache-aside SET for user recommendations (30-min TTL)."""
        self.set(f"recs:{user_id}", recs, ttl=ttl)

    def track_product_view(self, product_id: int):
        """Increment product view counter in sorted set (trending)."""
        self.zincrby("trending:views", 1.0, str(product_id))

    def get_trending(self, top_k: int = 20) -> List[Tuple[str, float]]:
        """Get trending products by view count."""
        return self.zrange("trending:views", 0, top_k - 1, reverse=True)

    # ── Monitoring ────────────────────────────────────────────────────────────

    def info(self) -> dict:
        """Mirrors Redis INFO command."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / max(total_requests, 1)
        with self._lock:
            return {
                "server":     "RedisCache (Simulation)",
                "keyspace":   {
                    "string_keys": len(self._store),
                    "hash_keys":   len(self._hstore),
                    "zset_keys":   len(self._zsets),
                },
                "stats": {
                    "total_commands_processed": total_requests,
                    "keyspace_hits":   self._hits,
                    "keyspace_misses": self._misses,
                    "hit_rate_pct":    round(hit_rate * 100, 2),
                    "total_sets":      self._total_set,
                    "evictions":       self._evictions,
                },
                "memory": {
                    "max_keys":  self._max_size,
                    "used_keys": len(self._store),
                    "policy":    "allkeys-lru",
                },
            }


# ─── Singleton instance ───────────────────────────────────────────────────────
_cache_instance: RedisCache = None


def get_cache() -> RedisCache:
    """Get the singleton Redis cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache(max_size=50_000, default_ttl=3600)
    return _cache_instance


if __name__ == "__main__":
    cache = get_cache()
    # Demo
    cache.set("user:42:prefs", {"theme": "dark", "lang": "en"}, ttl=300)
    print(cache.get("user:42:prefs"))
    cache.track_product_view(101)
    cache.track_product_view(101)
    cache.track_product_view(202)
    print("Trending:", cache.get_trending(5))
    print("Cache info:", json.dumps(cache.info(), indent=2))
