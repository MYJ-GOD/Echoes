# 已废弃文档归档

本目录保存已废弃但有历史参考价值的设计文档。

## 归档说明

| 文档 | 废弃原因 |
|---|---|
| `[已废弃] RAG_LangGraph 集成方案.md` | 原知识库 RAG 方案（文档级检索），已改为 Agent 记忆检索（对话记忆 + 记忆图谱），知识库 RAG 链路已从代码中移除 |
| `[已废弃] RAG_LangGraph_实施计划.md` | 同上，对应实施计划 |

## 当前方案

系统当前使用 **LangGraph ReAct Agent + 记忆检索质量工程**，检索对象为用户对话记忆（`conversation_history`），而非文档知识库。详见：
- [echoes-langgraph/README.md](../../echoes-langgraph/README.md)
- [Echoes_Architecture.md](../Echoes_Architecture.md)
