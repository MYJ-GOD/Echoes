"""bench/：阶段 -1 对话质量基准工具包（一次性评测工程，不进 15.2 依赖分层）。

职责：题集加载守卫、要点命中率与双通道分歧统计、provider CLI 编排。
真实 HTTP 通道（Ollama / OpenAI 兼容）由 scripts/bench_llm.py 本机驱动；CI 只测纯逻辑。
"""
from bench import client, runner, scoring  # noqa: F401
