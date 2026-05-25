"""
缓存管理器：语义向量缓存 + Redis 持久化。
"""
import hashlib
import json
import numpy as np
import redis
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class CacheManager:
    def __init__(self):
        self._redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self._similarity_threshold = 0.92
        self._ttl_seconds = 86400 * 7  # 7天过期

    def get_similar(self, query: str, prefix: str = "cache") -> dict | None:
        """通过语义相似度查找缓存命中"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        exact_key = f"{prefix}:exact:{query_hash}"
        exact = self._redis.get(exact_key)
        if exact:
            logger.info(f"Cache exact hit: {prefix}")
            return json.loads(exact)

        # 语义向量检索
        query_vec = self._model.encode(query)
        semantic_key = f"{prefix}:semantic:{query_hash}"
        candidates = self._redis.keys(f"{prefix}:semantic:*")
        for key in candidates:
            cached_vec_json = self._redis.get(key)
            if not cached_vec_json:
                continue
            cached_data = json.loads(cached_vec_json)
            cached_vec = np.array(cached_data["_vector"])
            similarity = np.dot(query_vec, cached_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(cached_vec)
            )
            if similarity >= self._similarity_threshold:
                logger.info(f"Cache semantic hit: {prefix}, similarity={similarity:.4f}")
                return cached_data["result"]

        return None

    def set(self, query: str, result: dict, prefix: str = "cache"):
        """缓存结果（精确+语义双写）"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        query_vec = self._model.encode(query)
        exact_key = f"{prefix}:exact:{query_hash}"
        semantic_key = f"{prefix}:semantic:{query_hash}"
        value = json.dumps(result, ensure_ascii=False)
        semantic_value = json.dumps({
            "_vector": query_vec.tolist(),
            "result": result,
        }, ensure_ascii=False)
        self._redis.setex(exact_key, self._ttl_seconds, value)
        self._redis.setex(semantic_key, self._ttl_seconds, semantic_value)
        logger.info(f"Cache set: {prefix}:{query_hash[:8]}")

    def invalidate(self, prefix: str = "cache"):
        """清除指定前缀的所有缓存"""
        keys = self._redis.keys(f"{prefix}:*")
        if keys:
            self._redis.delete(*keys)
            logger.info(f"Cache invalidated: {prefix} ({len(keys)} keys)")

    def health_check(self) -> bool:
        try:
            return self._redis.ping()
        except Exception:
            return False


# 全局单例
cache_manager = CacheManager()
