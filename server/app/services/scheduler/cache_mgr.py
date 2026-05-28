"""
语义向量缓存管理器：Sentence-BERT 语义相似度检索 + Redis 持久化。

缓存策略:
  - 精确匹配: MD5(query) → 直接命中（最快）
  - 语义匹配: S-BERT向量余弦相似度 → >= 0.92 阈值命中（减少重复LLM推理）

技术选型:
  - 模型: paraphrase-multilingual-MiniLM-L12-v2（轻量多语言S-BERT）
  - 存储: Redis（key: {prefix}:exact:{hash} / {prefix}:semantic:{hash}）
  - TTL: 7天自动过期
  - 相似度阈值: 0.92（余弦相似度，越接近1越相似）

用途:
  - LLM缺陷分析结果缓存: 相同缺陷组合不再重复调用Qwen3
  - LLM提示词优化结果缓存: 相似prompt分享优化结果

依赖:
  pip install sentence-transformers redis
"""
import hashlib
import json
import numpy as np
import redis
from loguru import logger
from sentence_transformers import SentenceTransformer

from app.core.config import settings


class CacheManager:
    """
    语义缓存管理器（单例）。

    用法:
      cached = cache_manager.get_similar(query, prefix="llm_defect")
      if not cached:
          result = llm_analyze(query)
          cache_manager.set(query, result, prefix="llm_defect")
    """

    def __init__(self):
        # Redis连接（DB 0 用于缓存）
        self._redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        # S-BERT多语言模型（384维向量）
        self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self._similarity_threshold = 0.92     # 语义相似度阈值
        self._ttl_seconds = 86400 * 7         # 缓存7天

    def get_similar(self, query: str, prefix: str = "cache") -> dict | None:
        """
        查找与查询语义相似的缓存结果。

        查找顺序:
          1. 精确匹配: MD5(query) 完全一致
          2. 语义检索: 遍历同prefix下的语义向量，余弦相似度 >= 0.92 命中

        参数:
            query:  查询文本（缺陷描述JSON / 提示词文本）
            prefix: 缓存键前缀（用于隔离不同业务缓存）

        返回:
            dict | None: 命中时返回缓存结果，未命中返回None
        """
        # 1. 精确匹配
        query_hash = hashlib.md5(query.encode()).hexdigest()
        exact_key = f"{prefix}:exact:{query_hash}"
        exact = self._redis.get(exact_key)
        if exact:
            logger.info(f"Cache exact hit: {prefix}")
            return json.loads(exact)

        # 2. 语义向量检索
        query_vec = self._model.encode(query)
        candidates = self._redis.keys(f"{prefix}:semantic:*")
        for key in candidates:
            cached_vec_json = self._redis.get(key)
            if not cached_vec_json:
                continue
            cached_data = json.loads(cached_vec_json)
            cached_vec = np.array(cached_data["_vector"])
            # 余弦相似度: dot(a,b) / (|a| * |b|)
            similarity = np.dot(query_vec, cached_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(cached_vec)
            )
            if similarity >= self._similarity_threshold:
                logger.info(f"Cache semantic hit: {prefix}, similarity={similarity:.4f}")
                return cached_data["result"]

        return None

    def set(self, query: str, result: dict, prefix: str = "cache"):
        """
        缓存结果（精确+语义双写策略）。

        参数:
            query:  查询文本
            result: 缓存结果dict
            prefix: 缓存键前缀
        """
        query_hash = hashlib.md5(query.encode()).hexdigest()
        query_vec = self._model.encode(query)

        # 精确缓存key
        exact_key = f"{prefix}:exact:{query_hash}"
        # 语义缓存key（存储向量用于相似度计算）
        semantic_key = f"{prefix}:semantic:{query_hash}"

        exact_value = json.dumps(result, ensure_ascii=False)
        semantic_value = json.dumps({
            "_vector": query_vec.tolist(),
            "result": result,
        }, ensure_ascii=False)

        self._redis.setex(exact_key, self._ttl_seconds, exact_value)
        self._redis.setex(semantic_key, self._ttl_seconds, semantic_value)
        logger.info(f"Cache set: {prefix}:{query_hash[:8]}")

    def invalidate(self, prefix: str = "cache"):
        """
        清除指定前缀的所有缓存。

        参数:
            prefix: 缓存键前缀（不传则清空所有缓存）
        """
        keys = self._redis.keys(f"{prefix}:*")
        if keys:
            self._redis.delete(*keys)
            logger.info(f"Cache invalidated: {prefix} ({len(keys)} keys)")

    def health_check(self) -> bool:
        """检查Redis缓存服务连通性。"""
        try:
            return self._redis.ping()
        except Exception:
            return False


# 全局单例
cache_manager = CacheManager()
