"""
缓存服务

提供：
- 查询向量缓存
- 检索结果缓存
- 对话历史缓存
- LLM 响应缓存

用于优化检索延迟，减少重复计算
"""
import logging
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目"""

    def __init__(self, value: Any, ttl_seconds: int = 300):
        self.value = value
        self.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        self.created_at = datetime.now()
        self.access_count = 0

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def access(self):
        self.access_count += 1


class QueryCache:
    """
    查询缓存

    缓存：
    - 查询文本 -> 向量
    - 查询 + 参数 -> 检索结果
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: int = 300,  # 5 分钟
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    entry.access()
                    return entry.value
                else:
                    # 过期条目，删除
                    del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = None):
        """设置缓存"""
        async with self._lock:
            # 检查是否需要清理
            if len(self._cache) >= self.max_size:
                await self._evict()

            self._cache[key] = CacheEntry(
                value,
                ttl_seconds=ttl or self.default_ttl,
            )

    async def delete(self, key: str):
        """删除缓存"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()

    async def _evict(self):
        """清理过期条目和最少访问条目"""
        # 删除过期条目
        expired_keys = [
            k for k, v in self._cache.items()
            if v.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]

        # 如果还是太多，删除最少访问的
        if len(self._cache) >= self.max_size:
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: (x[1].access_count, x[1].created_at),
            )
            # 删除 10% 最少访问的条目
            evict_count = max(1, self.max_size // 10)
            for key, _ in sorted_items[:evict_count]:
                del self._cache[key]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        now = datetime.now()
        valid_entries = sum(
            1 for e in self._cache.values()
            if not e.is_expired()
        )
        expired_entries = len(self._cache) - valid_entries
        total_accesses = sum(e.access_count for e in self._cache.values())

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "total_accesses": total_accesses,
            "max_size": self.max_size,
            "usage_percent": len(self._cache) / self.max_size * 100,
        }


class VectorCache(QueryCache):
    """向量缓存 - 专门缓存查询向量"""

    def __init__(self):
        super().__init__(max_size=5000, default_ttl=600)  # 10 分钟 TTL

    async def get_vector(self, query: str) -> Optional[List[float]]:
        """获取缓存的向量"""
        key = self._generate_key("query", query)
        return await self.get(key)

    async def set_vector(self, query: str, vector: List[float]):
        """缓存向量"""
        key = self._generate_key("query", query)
        await self.set(key, vector)


class RetrievalCache(QueryCache):
    """检索结果缓存"""

    def __init__(self):
        super().__init__(max_size=3000, default_ttl=180)  # 3 分钟 TTL

    async def get_results(
        self,
        query: str,
        kb_ids: List[str],
        top_k: int,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的检索结果"""
        key = self._generate_key("retrieval", query, kb_ids, top_k)
        return await self.get(key)

    async def set_results(
        self,
        query: str,
        kb_ids: List[str],
        top_k: int,
        results: List[Dict[str, Any]],
    ):
        """缓存检索结果"""
        key = self._generate_key("retrieval", query, kb_ids, top_k)
        await self.set(key, results)


class ResponseCache(QueryCache):
    """LLM 响应缓存"""

    def __init__(self):
        super().__init__(max_size=2000, default_ttl=600)  # 10 分钟 TTL

    async def get_response(
        self,
        query: str,
        context_hash: str,
    ) -> Optional[List[str]]:
        """获取缓存的响应"""
        key = self._generate_key("response", query, context_hash)
        return await self.get(key)

    async def set_response(
        self,
        query: str,
        context_hash: str,
        response: List[str],
    ):
        """缓存响应"""
        key = self._generate_key("response", query, context_hash)
        await self.set(key, response)


# 全局缓存实例
_vector_cache: Optional[VectorCache] = None
_retrieval_cache: Optional[RetrievalCache] = None
_response_cache: Optional[ResponseCache] = None


def get_vector_cache() -> VectorCache:
    """获取向量缓存实例"""
    global _vector_cache
    if _vector_cache is None:
        _vector_cache = VectorCache()
    return _vector_cache


def get_retrieval_cache() -> RetrievalCache:
    """获取检索结果缓存实例"""
    global _retrieval_cache
    if _retrieval_cache is None:
        _retrieval_cache = RetrievalCache()
    return _retrieval_cache


def get_response_cache() -> ResponseCache:
    """获取响应缓存实例"""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache()
    return _response_cache


# ========== 装饰器 ==========

def cache_vector(ttl: int = 600):
    """
    向量缓存装饰器

    Usage:
        @cache_vector()
        async def generate_embedding(query: str) -> List[float]:
            ...
    """
    async def decorator(func):
        cache = get_vector_cache()

        async def wrapper(query: str, *args, **kwargs):
            # 尝试从缓存获取
            cached = await cache.get_vector(query)
            if cached is not None:
                logger.debug(f"Vector cache hit: {query[:50]}...")
                return cached

            # 执行函数
            result = await func(query, *args, **kwargs)

            # 缓存结果
            await cache.set_vector(query, result)
            logger.debug(f"Vector cache set: {query[:50]}...")

            return result

        return wrapper
    return decorator


def cache_retrieval(ttl: int = 180):
    """
    检索结果缓存装饰器

    Usage:
        @cache_retrieval()
        async def search_knowledge(...) -> List[Dict]:
            ...
    """
    async def decorator(func):
        cache = get_retrieval_cache()

        async def wrapper(
            query_vector,
            query_text: str,
            kb_ids: List[str],
            top_k: int,
            *args,
            **kwargs
        ):
            # 尝试从缓存获取
            cached = await cache.get_results(query_text, kb_ids, top_k)
            if cached is not None:
                logger.debug(f"Retrieval cache hit: {query_text[:50]}...")
                return cached

            # 执行函数
            result = await func(
                query_vector,
                query_text,
                kb_ids,
                top_k,
                *args,
                **kwargs
            )

            # 缓存结果
            await cache.set_results(query_text, kb_ids, top_k, result)
            logger.debug(f"Retrieval cache set: {query_text[:50]}...")

            return result

        return wrapper
    return decorator


async def get_cache_stats() -> Dict[str, Any]:
    """获取所有缓存的统计信息"""
    return {
        "vector_cache": get_vector_cache().get_stats(),
        "retrieval_cache": get_retrieval_cache().get_stats(),
        "response_cache": get_response_cache().get_stats(),
    }


async def clear_all_caches():
    """清空所有缓存"""
    await get_vector_cache().clear()
    await get_retrieval_cache().clear()
    await get_response_cache().clear()
    logger.info("All caches cleared")
