"""engines/：ASR / TTS / LLM 引擎（3.3）。

engines 禁止 import session/orchestration（15.2 分层合同）——保证引擎可独立测试与替换；
具体引擎只在组合根实例化（3.2「组装归组合根」）。
"""
