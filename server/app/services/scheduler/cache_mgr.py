"""
语义向量缓存管理器：Sentence-BERT 语义相似度检索 + Redis 持久化。

缓存策略:
  - 精确匹配: MD5(query) → 直接命中（最快）
  - 语义匹配: S-BERT向量余弦相似度 → >= 0.92 阈值命中（需模型可用）

模型加载失败时自动降级为纯精确匹配模式，不阻塞服务启动。

用法:
  cached = cache_manager.get_similar(query, prefix="llm_defect")
  if not cached:
      result = llm_analyze(query)
      cache_manager.set(query, result, prefix="llm_defect")
"""
import hashlib
import json
import redis
from loguru import logger

from app.core.config import settings


class CacheManager:
    """语义缓存管理器（单例），模型不可用时降级为精确匹配。"""

    def __init__(self):
        self._redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        self._model = None           # S-BERT 模型实例（懒加载）
        self._model_load_attempted = False
        self._similarity_threshold = 0.92
        self._ttl_seconds = 86400 * 7

    def _try_load_model(self):
        """尝试加载 S-BERT 模型，失败时标记不可用。"""
        if self._model_load_attempted:
            return
        self._model_load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            logger.info("Sentence-BERT model loaded, semantic cache enabled")
        except Exception as e:
            logger.warning(f"S-BERT model unavailable, semantic cache disabled: {e}")

    def get_similar(self, query: str, prefix: str = "cache") -> dict | None:
        """
        查找与查询语义相似的缓存结果（先精确匹配，再语义检索）。

        参数:
            query:  查询文本
            prefix: 缓存键前缀
        返回:
            dict | None: 命中时返回缓存结果，未命中返回 None
        """
        # 1. 精确匹配
        query_hash = hashlib.md5(query.encode()).hexdigest()
        exact_key = f"{prefix}:exact:{query_hash}"
        exact = self._redis.get(exact_key)
        if exact:
            logger.info(f"Cache exact hit: {prefix}")
            return json.loads(exact)

        # 2. 语义向量检索（模型不可用时跳过）
        self._try_load_model()
        if self._model is None:
            return None

        import numpy as np
        query_vec = self._model.encode(query)
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
        """缓存结果（精确+语义双写）。语义写仅在模型可用时生效。"""
        query_hash = hashlib.md5(query.encode()).hexdigest()

        # 精确缓存
        exact_key = f"{prefix}:exact:{query_hash}"
        exact_value = json.dumps(result, ensure_ascii=False)
        self._redis.setex(exact_key, self._ttl_seconds, exact_value)

        # 语义缓存（模型可用时写入向量）
        self._try_load_model()
        if self._model is not None:
            import numpy as np
            query_vec = self._model.encode(query)
            semantic_key = f"{prefix}:semantic:{query_hash}"
            semantic_value = json.dumps({
                "_vector": query_vec.tolist(),
                "result": result,
            }, ensure_ascii=False)
            self._redis.setex(semantic_key, self._ttl_seconds, semantic_value)

    def invalidate(self, prefix: str = "cache"):
        """清除指定前缀的所有缓存。"""
        keys = self._redis.keys(f"{prefix}:*")
        if keys:
            self._redis.delete(*keys)
            logger.info(f"Cache invalidated: {prefix} ({len(keys)} keys)")

    def health_check(self) -> bool:
        """检查 Redis 缓存服务连通性。"""
        try:
            return self._redis.ping()
        except Exception:
            return False


# 全局单例
cache_manager = CacheManager()
