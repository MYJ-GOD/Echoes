"""
Guardrail 模型 - 安全护栏

用于检测敏感/违规内容
"""
import re
from pydantic import BaseModel
from typing import Literal


class GuardrailResult(BaseModel):
    """Guardrail 检查结果"""
    passed: bool
    message: str = ""
    block_reason: str = ""


# 敏感词列表（政治、暴力、色情等）
SENSITIVE_KEYWORDS = [
    # 暴力相关
    "自杀", "自残", "杀人", "炸弹制作", "枪支制造",
    # 色情相关
    "色情", "裸体", "性爱",
    # 违法相关
    "毒品制作", "赌博网站", "洗钱方法",
    # 侮辱性词汇
    "去死", "废物",
]

# 正则模式匹配（更灵活的检测）
SENSITIVE_PATTERNS = [
    # 诱导性 prompt 注入
    r"(?i)ignore\s+(all\s+)?previous\s+instructions",
    r"(?i)你是一个.*?(忽略|忘记).*?规则",
    # 个人信息泄露请求
    r"(?i)(给我|提供|告诉我).{0,10}(密码|身份证|银行卡|社保)",
    # 攻击性指令
    r"(?i)(如何|怎么).{0,10}(黑进|入侵|攻击|破解)",
]


async def check_guardrail(query: str) -> GuardrailResult:
    """
    检查查询是否通过安全护栏

    Args:
        query: 用户查询

    Returns:
        检查结果
    """
    # 0. 空查询检查
    if not query or len(query.strip()) == 0:
        return GuardrailResult(
            passed=False,
            message="查询不能为空",
            block_reason="empty_query",
        )

    # 1. 长度检查
    if len(query) > 5000:
        return GuardrailResult(
            passed=False,
            message="查询过长，请控制在 5000 字以内",
            block_reason="too_long",
        )

    # 2. 敏感词检查
    query_lower = query.lower()
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in query_lower:
            return GuardrailResult(
                passed=False,
                message="查询包含不当内容",
                block_reason="sensitive_content",
            )

    # 3. 正则模式检查
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, query):
            return GuardrailResult(
                passed=False,
                message="查询包含不当内容",
                block_reason="sensitive_pattern",
            )

    # 4. 纯特殊字符/无意义输入
    cleaned = re.sub(r'[\s\W]', '', query)
    if len(cleaned) == 0:
        return GuardrailResult(
            passed=False,
            message="请输入有效内容",
            block_reason="invalid_input",
        )

    return GuardrailResult(
        passed=True,
        message="通过检查",
    )
