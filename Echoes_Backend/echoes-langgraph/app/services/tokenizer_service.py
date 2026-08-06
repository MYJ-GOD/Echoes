"""
分词服务

提供文本分词和词汇表索引功能
"""
import logging
import hashlib
from typing import List, Tuple, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


# 全局词汇表索引
_vocabulary: Dict[str, int] = {}
_next_index = 0


def _get_or_create_index(token: str) -> int:
    """获取或创建词的索引"""
    global _next_index
    if token not in _vocabulary:
        _vocabulary[token] = _next_index
        _next_index += 1
    return _vocabulary[token]


async def tokenize_with_indices(text: str) -> List[Tuple[str, int]]:
    """
    文本分词并返回词及其索引

    Args:
        text: 输入文本

    Returns:
        (词，索引) 元组列表
    """
    tokens = _tokenize(text)
    return [(token, _get_or_create_index(token)) for token in tokens]


def _tokenize(text: str) -> List[str]:
    """
    文本分词

    支持:
    - 英文：按空格分词
    - 中文：简单按字符分词

    TODO: 集成 jieba 或其他中文分词库
    """
    import re
    # 提取所有字母数字和中文字符
    tokens = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
    return [t for t in tokens if len(t) > 0]


def get_vocabulary_size() -> int:
    """获取词汇表大小"""
    return len(_vocabulary)


def clear_vocabulary():
    """清空词汇表（用于测试）"""
    global _vocabulary, _next_index
    _vocabulary = {}
    _next_index = 0
