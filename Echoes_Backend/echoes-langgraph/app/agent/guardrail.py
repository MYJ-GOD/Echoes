"""
Guardrail 安全门禁

入口第一关：关键词黑名单 + System Prompt 双重过滤
命中红线 → 直接拦截，返回安全兜底回复，不进入 Agent workflow
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 关键词黑名单（示例，实际应配置化 + 定期更新）
BLOCKED_KEYWORDS = [
    "自杀", "伤害自己", "结束生命", "想死",
    "制作炸弹", "购买毒品", "非法交易",
    "色情", "裸聊", "约炮",
]

SAFE_FALLBACK_RESPONSE = "抱歉，我无法回答这个问题。如果你遇到困扰，建议寻求专业帮助（心理热线：400-161-9995）。"


def check_guardrail(query: str) -> Optional[str]:
    """Guardrail 检查：关键词黑名单过滤

    Args:
        query: 用户输入

    Returns:
        None: 通过检查，可以继续
        str: 命中红线，返回兜底回复（调用方直接返回给用户）
    """
    query_lower = query.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in query_lower:
            logger.warning("Guardrail 拦截：命中关键词 '%s' | query='%s'", keyword, query[:50])
            return SAFE_FALLBACK_RESPONSE
    return None
