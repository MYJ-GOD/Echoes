"""core/：零依赖类型层（文档 3.3/15.2）——错误码、状态机、AudioChunk 等。

依赖方向：core 不 import 任何上层；全工程唯一 pydantic 例外在 ipc/（15.2 v1.4）。
"""
