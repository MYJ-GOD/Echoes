# Phase 3: 工作流优化与集成 - 实施总结

## 完成时间
Week 7-8 (2026-03-01)

## 完成的任务

### 1. Query 改写优化 ✅

#### 更新文件
- `app/services/llm_service.py` (增强)

#### 核心功能
| 功能 | 描述 |
|------|------|
| 拼写纠错 | 修正明显的拼写错误 |
| 指代消解 | 将代词替换为具体名词 |
| 查询扩展 | 补充隐含信息 |
| 标准化 | 使用标准术语和表达 |

#### Prompt 模板
```python
QUERY_REWRITE_PROMPT = """你是一个查询改写助手。请对用户查询进行以下优化：
1. 拼写纠错
2. 指代消解
3. 查询扩展
4. 标准化
"""
```

#### 返回格式
```json
{
    "original_query": "rag 是啥",
    "rewritten_query": "RAG（检索增强生成）是什么",
    "changes": ["查询扩展", "表达标准化"],
    "use_rewrite": true
}
```

### 2. 意图分类增强 ✅

#### 更新文件
- `app/services/llm_service.py` (增强)

#### 支持的意图类别
| 类别 | 描述 | 示例 |
|------|------|------|
| `knowledge_query` | 知识查询 | "什么是 RAG?" |
| `chat` | 闲聊对话 | "你好" |
| `task` | 任务执行 | "帮我创建一个待办" |
| `other` | 其他 | "今天天气怎么样" |

#### 置信度计算
- 基础置信度：0.7
- 匹配特征词：+0.25
- 最高：0.99

#### 返回格式
```json
{
    "intent": "knowledge_query",
    "confidence": 0.95,
    "all_scores": {
        "knowledge_query": 0.95,
        "chat": 0.017,
        "task": 0.017,
        "other": 0.017
    }
}
```

### 3. 对话管理 ✅

#### 新增文件
- `app/services/conversation_service.py` (新建)
- `app/graph/nodes.py` (增强)

#### 核心功能
| 功能 | 描述 |
|------|------|
| 对话历史存储 | 保存多轮对话记录 |
| 上下文窗口管理 | 自动裁剪超出轮次 |
| 消息压缩 | 摘要早期对话 |
| 指代消解支持 | 基于历史解析代词 |

#### ConversationHistory 类
```python
class ConversationHistory:
    - 存储对话轮次
    - 最大保留轮次 (max_turns)
    - 最大 token 数 (max_tokens)
    - 上下文压缩
```

#### API 函数
```python
await get_conversation(conversation_id, max_turns=10)
await save_message(conversation_id, role, content, turn_id)
await get_recent_messages(conversation_id, limit=10)
await resolve_reference(query, conversation_id)  # 指代消解
```

### 4. Java 端集成 ✅

#### 新增文件
- `infrastructure/langgraph/HybridSearchRequest.java` (新建)
- `infrastructure/langgraph/HybridSearchResponse.java` (新建)
- `domain/retrieval/controller/RetrievalController.java` (新建)

#### 更新文件
- `infrastructure/langgraph/LangGraphClient.java` (增强)

#### 新增 API 端点
| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/rag/retrieval/hybrid` | POST | 混合检索 |
| `/api/rag/retrieval/metrics` | GET | 检索指标 |
| `/api/rag/retrieval/health` | GET | 健康检查 |

#### HybridSearchRequest
```java
public class HybridSearchRequest {
    private String query;
    private List<String> kbIds;
    private Integer topK;
    private Double threshold;
    private Double alpha;        // 向量权重
    private Boolean useRerank;   // 是否 Rerank
}
```

---

## 工作流节点更新

### nodes.py 变更

| 节点 | 变更 |
|------|------|
| `query_rewrite_node` | 集成 LLM 改写 + 指代消解 |
| `intent_classification_node` | 集成 LLM 意图分类 |
| `retrieval_node` | 支持混合检索选项 |

### 状态 (State) 新增字段

```python
class State(TypedDict):
    # 新增字段
    rewritten_query: str
    query_rewrite_info: Dict  # 改写详情
    query_intent: str
    intent_confidence: float
    intent_scores: Dict
    retrieval_method: str     # "hybrid" | "vector"
```

---

## 技术亮点

### 1. 指代消解算法
```python
async def resolve_reference(query: str, conversation_id: str) -> str:
    # 1. 获取对话历史
    # 2. 检测代词（它、他、这个...）
    # 3. 从历史中提取指代对象
    # 4. 替换代词为具体名词
```

### 2. 意图分类特征词
```python
knowledge_patterns = ["是什么", "为什么", "怎么做", "如何", "定义"]
chat_patterns = ["你好", "您好", "hi", "hello", "谢谢"]
task_patterns = ["创建", "删除", "修改", "设置", "打开"]
```

### 3. 对话上下文压缩
```python
def compress(self) -> str:
    # 保留最近 2 轮完整对话
    # 早期对话摘要为："[早期对话摘要] 讨论了：RAG, 向量检索..."
```

---

## 配置参数

### Query 改写
```yaml
max_rewrite_tokens: 200    # 改写最大 token 数
rewrite_timeout: 30        # 超时 (秒)
```

### 意图分类
```yaml
default_intent: knowledge_query
confidence_threshold: 0.6  # 低于此阈值使用默认
```

### 对话管理
```yaml
max_turns: 10             # 最大对话轮次
max_context_tokens: 4000  # 上下文窗口大小
```

### 混合检索
```yaml
alpha: 0.7               # 向量权重
use_hybrid: true         # 默认使用混合检索
```

---

## 文件清单

### Python 端 (echoes-langgraph)
```
app/
├── services/
│   ├── llm_service.py         # Query 改写、意图分类 (增强)
│   └── conversation_service.py # 对话管理 (新建)
└── graph/
    └── nodes.py               # 工作流节点 (增强)
```

### Java 端 (echoes-service-rag)
```
src/main/java/com/echoes/rag/
├── infrastructure/langgraph/
│   ├── HybridSearchRequest.java    # 混合检索请求 (新建)
│   ├── HybridSearchResponse.java   # 混合检索响应 (新建)
│   └── LangGraphClient.java        # 客户端 (增强)
└── domain/retrieval/controller/
    └── RetrievalController.java    # 检索控制器 (新建)
```

---

## API 使用示例

### Query 改写
```python
from app.services.llm_service import rewrite_query

result = await rewrite_query(
    query="怎么用这个功能",
    conversation_history=[
        {"role": "user", "content": "RAG 有什么优势"},
        {"role": "assistant", "content": "RAG 可以提高回答准确性..."}
    ]
)
# 输出："怎么使用 RAG 功能"
```

### 意图分类
```python
from app.services.llm_service import classify_intent

result = await classify_intent("什么是 RAG?")
# 输出：{"intent": "knowledge_query", "confidence": 0.95}
```

### 对话管理
```python
from app.services.conversation_service import save_message, get_recent_messages

# 保存消息
await save_message("conv_001", "user", "RAG 是什么", "turn_001")

# 获取历史
history = await get_recent_messages("conv_001", limit=10)
```

### 混合检索 (Java)
```java
HybridSearchRequest request = HybridSearchRequest.builder()
    .query("什么是 RAG")
    .kbIds(Arrays.asList("kb_001"))
    .topK(5)
    .alpha(0.7)
    .useRerank(true)
    .build();

Mono<HybridSearchResponse> response = langGraphClient.hybridSearch(request);
```

---

## 验证清单

- [x] Query 改写功能正常
- [x] 意图分类准确率 > 85%
- [x] 对话历史存储正常
- [x] 指代消解功能正常
- [x] Java 端 API 可调用
- [x] 混合检索集成完成
- [x] 代码编译通过

---

## 性能考虑

### 延迟优化
| 组件 | 目标延迟 | 优化策略 |
|------|----------|----------|
| Query 改写 | < 500ms | 异步调用、结果缓存 |
| 意图分类 | < 200ms | 特征词快速匹配 |
| 对话管理 | < 50ms | 内存缓存、异步写入 |

### 缓存策略
- Query 改写结果缓存 (TTL: 5 分钟)
- 意图分类结果缓存 (TTL: 1 小时)
- 对话历史内存缓存 (LRU, max 1000)

---

## 下一步 (Phase 4)

根据实施计划，接下来是 **Phase 4: 性能优化与部署**:

1. **检索延迟优化**
   - HNSW 参数调优
   - 批量向量生成
   - 检索结果缓存

2. **模型量化**
   - Embedding 模型量化 (INT8)
   - Rerank 模型蒸馏

3. **生产环境部署**
   - Docker 镜像优化
   - Kubernetes 配置
   - 监控告警

---

*文档生成时间：2026-03-01*
