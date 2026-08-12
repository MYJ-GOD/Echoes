"""
意图识别路由（正则规则 + 语义向量库）

三级策略（快 → 准）：
1. 正则规则：高置信关键词/模板，命中直接返回（最快，零成本）
2. 语义向量库：semantic-router + bge-m3，样本相似度匹配（快，无 LLM）
3. LLM 兜底：前两级都未命中时，交给 planner 的 LLM 判断（准，慢）

意图类别与 planner 一致：chat / emotional_support / memory_recall / profile_query / task
"""
import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ============== 1. 正则规则库（高置信，优先匹配）==============
INTENT_REGEX_RULES = {
    "memory_recall": [
        r"还记得", r"你说过", r"我之前", r"上次(说|提|讲)", r"记不记得", r"我告诉过你",
    ],
    "emotional_support": [
        r"好难过", r"想哭", r"压力(好|太)?大", r"很焦虑", r"好累", r"撑不下去",
        r"心情(不好|很差|低落)", r"好烦", r"抑郁",
    ],
    "profile_query": [
        r"我是(个|什么)", r"你(觉得|眼中)的我", r"我的性格", r"我这个人",
    ],
}


def match_by_regex(query: str) -> Optional[str]:
    """正则规则匹配意图，命中返回 intent，否则 None"""
    for intent, patterns in INTENT_REGEX_RULES.items():
        for p in patterns:
            if re.search(p, query):
                logger.info("意图正则命中: intent=%s pattern=%s", intent, p)
                return intent
    return None


# ============== 2. 语义向量库（semantic-router + bge-m3）==============
_router = None


class _BgeM3Encoder:
    """包装项目已有的 bge-m3（sentence-transformers），供 semantic-router 使用。

    继承 semantic_router.encoders.DenseEncoder，复用本地缓存模型（不联网、不重下）。
    """

    def __new__(cls):
        # 延迟导入，避免模块加载即拉起 semantic_router
        from semantic_router.encoders import DenseEncoder

        class BgeM3Encoder(DenseEncoder):
            def __init__(self):
                super().__init__(name="bge-m3-local", score_threshold=0.5)

            def __call__(self, docs: List[str]) -> List[List[float]]:
                from app.services.embedding_service import get_embedding_model
                model = get_embedding_model()
                embs = model.encode(docs, normalize_embeddings=True)
                return embs.tolist()

            async def acall(self, docs: List[str]) -> List[List[float]]:
                return self.__call__(docs)

        return BgeM3Encoder()


# 每个意图的样本话术（语义库的“训练样本”，非规则）
INTENT_SAMPLES = {
    "memory_recall": [
        "你还记得我喜欢喝什么吗", "我上次跟你说的那件事", "你记得我的生日吗", "之前聊过的话题",
    ],
    "emotional_support": [
        "我今天心情特别差", "感觉整个人都不好了", "最近压力好大喘不过气", "好想有人陪陪我",
    ],
    "profile_query": [
        "你觉得我是个怎样的人", "在你眼里我是什么样的", "帮我分析下我的性格",
    ],
    "task": [
        "帮我记住这件事", "提醒我明天做什么", "记录一下我的偏好",
    ],
    "chat": [
        "今天天气真好", "你在干嘛呢", "随便聊聊吧", "讲个笑话听听",
    ],
}


def _build_router():
    """构建 semantic-router（懒加载，首次调用时初始化）"""
    global _router
    if _router is not None:
        return _router
    try:
        from semantic_router import Route, SemanticRouter

        routes = [
            Route(name=intent, utterances=samples)
            for intent, samples in INTENT_SAMPLES.items()
        ]
        encoder = _BgeM3Encoder()
        _router = SemanticRouter(encoder=encoder, routes=routes, auto_sync="local")
        logger.info("语义意图路由已初始化（semantic-router + bge-m3）")
        return _router
    except Exception as e:
        logger.warning("语义路由初始化失败，将降级到 LLM: %s", e)
        return None


def match_by_semantic(query: str) -> Optional[str]:
    """语义向量匹配意图，命中返回 intent，否则 None"""
    router = _build_router()
    if router is None:
        return None
    try:
        result = router(query)
        if result and result.name:
            logger.info("意图语义命中: intent=%s", result.name)
            return result.name
    except Exception as e:
        logger.warning("语义意图匹配失败: %s", e)
    return None


# ============== 对外统一接口 ==============
def classify_intent(query: str) -> Optional[str]:
    """两级意图识别：正则 → 语义向量。都未命中返回 None（交给 LLM 兜底）"""
    if not query or not query.strip():
        return None
    # 1. 正则规则（最快）
    intent = match_by_regex(query)
    if intent:
        return intent
    # 2. 语义向量库
    intent = match_by_semantic(query)
    if intent:
        return intent
    # 3. 未命中 → None（planner 用 LLM 判断）
    return None
