# Echoes 架构文档集

> 本文档集包含三部分：
>
> 1️⃣ **统一中期架构文档**（融合原中期 + 原后期，不引入 LangGraph）  
> 2️⃣ **后期架构发展文档（LangGraph 完全体）**  
> 3️⃣ **架构与约束文档（全阶段适用 · 强红线）**

---

## 第一部分：统一中期架构发展文档

> **状态：稳定 · 可规模化 · 无 LangGraph**

---

### 1. 文档定位

本阶段为 Echoes 的统一中期阶段，融合原「中期架构发展文档」与「后期架构发展文档」中不引入 LangGraph 的全部内容。

该阶段目标是：

- 从“功能可用”演进到“工程可规模化”
- 系统在真实并发下行为稳定、可预测、可回滚
- 为后期引入 LangGraph 打好工程与边界基础

本阶段为**强执行约束文档**。

---

### 2. 中期核心目标（统一）

- 架构边界清晰，职责单一  
- 承载更高并发与更稳定的 TTS 生成  
- 支持长文本 / 高并发音频生产  
- 强化稳定性、降级与可运维能力  
- 用户体验始终由 Java 单一出口统一治理  

---

### 3. 架构总原则（中期红线）

#### 3.1 分层与职责

**Java（对外治理与编排层）**

- 唯一对外入口  
- 会话 / 用户 / Conversation 管理  
- SSE 输出与顺序控制（`seq` 单点生成）  
- 分句 / 分段策略主控  
- 同步 / 异步（Job）策略选择  
- 取消 / 中断 / 丢弃 / 降级决策  

**Python（能力执行层）**

- LLM / TTS / ASR 执行  
- 不直接面向前端  
- 不暴露 SSE  
- 不维护跨轮会话状态  
- 不进行流程跳转决策  

---

#### 3.2 接口与协议原则

- 所有对外 URL **永远不带版本号**
- 协议演进通过 `schema_version / protocol_version`
- 新字段只追加，不删除、不重命名

**对外唯一流式接口：**

```
POST /conversation/chat-stream
```

**对外禁止出现：**

- `/voice/**`
- `/internal/**`

---

### 4. 异步体系（中期完成态）

#### 4.1 同步能力

- 同步 TTS：短文本 / 低延迟场景  
- Java 同步调用 Python  
- Java 负责结果分发  

#### 4.2 异步 Jobs（中期增强能力）

- 用于长文本 / 高并发场景  
- Java 投递 Job  
- Job 支持：幂等 / 重试 / 取消  
- Job 结果必须回流至 Java  
- 前端永远感知不到 Job 的存在  

**Job 明确不允许：**

- 维护会话状态  
- 决定输出节奏  
- 直接输出 SSE  

---

### 5. 流式输出治理（SSE）

- 对外 SSE 只有一个入口  
- `seq` 只能由 Java 生成  
- Python 仅返回执行结果  

Java 负责：

- 防止重复播报  
- 丢弃过期结果  
- 用户中断后的资源回收  

---

### 5.x 幂等语义与 Turn 权威模型（强约束）

#### 5.x.1 核心标识分工

**turn_id（权威）**

- 表示“一次用户输入（turn）”
- 业务语义主键
- 用于端到端追踪、输出复用、Job 一致性
- 是服务端最终一致的唯一依据

**idempotency_key（输入侧幂等）**

- 用于客户端弱网重试 / 网关重放保护
- 默认等于 `turn_id`
- 不作为业务幂等依据

**强约束：**

- `turn_id` 是唯一权威幂等主键  
- `idempotency_key` 仅用于输入侧防抖  

---

#### 5.x.2 turn_id 生成责任

- 必须由客户端生成  
- 同一次用户输入生命周期内保持不变  

推荐格式：

- UUIDv7 / ULID / Snowflake  

**禁止：**

- 服务端补生成 `turn_id`
- 重试时更换 `turn_id`

---

#### 5.x.3 chat-stream 幂等行为（写死）

**规则 A：同 `conversationId` + 同 `turn_id`**

- 已完成 → REPLAY（重放已存事件）
- 进行中 → ATTACH（仅推送后续事件）
- 已取消 / 失败 → 重放 `error + end`
- 仅当 `force_new_turn=true` 才允许新建 turn

**规则 B：同 `idempotency_key`，不同 `turn_id`**

- 返回 `409 Conflict`
- `error.details` 返回 `existing_turn_id`

**规则 C：同 `turn_id`，payload 不一致**

- 返回 `409 Conflict`
- `error.details` 返回 `mismatch_fields`

---

#### 5.x.4 Turn 事件日志

服务端必须维护 `turn_event_log`：

字段：

- `seq`（Java 单点生成）
- `type`
- `data`
- `ts`

`type` 枚举固定：

- message.delta
- message.final
- audio.chunk
- error
- end

TTL：24h ～ 7d（至少覆盖弱网重连）

---

### 5.y SSE error / end 事件最小契约

#### 5.y.1 error 事件

```json
{
  "code": "STRING_ENUM",
  "message": "HUMAN_READABLE",
  "retryable": true,
  "stage": "JAVA_ORCHESTRATOR | PY_EXECUTOR | LLM | TTS | ASR | STORAGE | NETWORK",
  "http_status": 400,
  "details": {},
  "suggested_action": "RETRY | REFRESH | CONTACT_SUPPORT | NONE"
}
```

---

#### 5.y.2 end 事件

```json
{
  "status": "SUCCESS | FAILED | CANCELLED",
  "usage": { "input_tokens": 0, "output_tokens": 0 },
  "latency_ms": 0,
  "final_message_id": "..."
}
```

---

#### 5.y.3 end 送达边界

- 尽最大努力发送  
- 不承诺 100% 必达  

---

### 5.z SSE 断线重连与续播

- 支持 `Last-Event-ID`
- 支持 `resume_from_seq`
- 补发缺失事件后继续 live 推送  

日志过期返回：

- `error(code=RESUME_NOT_AVAILABLE)`

---

### 5.w messages 接口硬约束

```
GET /conversation-session/{conversationId}/messages
```

只允许：

- 最终 user / assistant 消息
- 最终文本 / 音频引用  

禁止：

- streaming
- progress
- job_status
- partial_text
- 任何执行态字段  

---

### 5.v Voice-Ref 上传规范

```
POST /conversation/voice-ref/upload
```

- refId 绑定 user_id（可选绑定 conversationId）
- TTL：24h ～ 7d
- 最大 10MB
- 支持 wav / mp3 / m4a（16k / mono）

错误码：

- INVALID_AUDIO_FORMAT
- PAYLOAD_TOO_LARGE
- UNSUPPORTED_MEDIA_TYPE
- RATE_LIMITED
- INTERNAL_ERROR

---

### 5.u 音色选择强约束（新增硬约束）

- 当会话已绑定 `voiceAssetId` 时，推理链路必须使用该音色。
- 禁止静默回退到 `default`。
- 若音色不可用（`.pt` 缺失 / 权限不足 / 资源未加载），必须返回 `error` 事件，不允许返回“成功但默认音色”。
- 流式错误事件最小要求：
  - `code`: `VOICE_NOT_AVAILABLE` 或 `VOICE_STREAM_FAILED`
  - `details.voice_asset_id`
  - `retryable`（布尔）
- UI 必须显示“当前生效音色 ID”；若会话已绑定音色，联系人列表不再显示“选择音色”按钮。

---

### 5.t 流式链路可观测与 SLO（新增验收标准）

链路定义：`conversation -> voice -> Echoes-AI -> client`

必备透传头：

- `X-TRACE-ID`
- `X-SESSION-ID`
- `X-TURN-ID`
- `X-USER-ID`

必备指标（按天统计）：

- `tts_stream_success_rate`
- `tts_stream_empty_audio_rate`
- `tts_stream_first_chunk_latency_ms`（P50/P95/P99）
- `tts_stream_connection_reset_count`

最低验收门槛（中期）：

- 连续 100 次流式对话，音频成功率 `>= 99%`
- 空音频率 `< 1%`
- 首包时延 P95 `< 2000ms`（本地环境可放宽但需留痕）

---

### 5.s 多租户与鉴权红线（新增硬约束）

- 核心链路禁止 `X-USER-ID` 为空；为空必须拒绝或在网关补全，不得继续执行业务。
- 音色资产访问必须校验 `owner/grant`。
- 所有内部调用接口必须带 `X-INTERNAL=1`，对外网关禁止直连内部路由。
- 训练、推理、下载均需产出审计日志：`user_id`、`voice_asset_id`、`turn_id`、`result`。

---

## 架构兜底结论

Echoes 承诺的是**用户感知上的 exactly-once**，  
而非底层物理 exactly-once。

一切能力增强（包括 LangGraph）  
不得破坏 **Java 单一出口、SSE 单一入口与 turn_id 权威模型**。

---

## 第二部分：后期架构发展文档（LangGraph 完全体）

> **状态：规划中 · 以第一部分为前置**

### 1. 引入前置条件（全部满足才可进入）

- 第一部分 SLO 连续 2 周稳定达标
- 音色强约束已上线且无静默回退
- 端到端追踪（trace/session/turn/user）稳定可用

### 2. LangGraph 引入边界

- LangGraph 仅负责**编排**，不替代 Java 对外单一出口。
- 对外流式接口仍是：`POST /conversation/chat-stream`
- `turn_id` 权威模型不变；`seq` 仍由 Java 单点生成。

### 3. 最小图建议

- `guardrail -> rewrite -> retrieve -> rank -> generate -> grounding_check -> stream_out`
- 检索为空时可降级到纯生成，但必须带降级标记。

### 4. 不可破坏项

- 不新增对外 `/internal/**` 暴露
- 不在 Python/Graph 层直接输出 SSE 给前端
- 不绕过 Java 的幂等与事件日志体系

---

## 第三部分：架构与约束文档（全阶段适用 · 强红线）

### A. 统一错误码规范（最低集合）

- `VOICE_NOT_AVAILABLE`
- `VOICE_STREAM_FAILED`
- `RESUME_NOT_AVAILABLE`
- `PERMISSION_DENIED`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

### B. 统一发布门禁

- 编译通过（Java/Python）
- 核心回归通过（会话、流式、训练、音色选择）
- 指标达标（参考 5.t）

### C. 统一变更约束

- 新能力只能“追加”，不得破坏既有协议字段含义
- 任何降级必须可观测、可告警、可追踪
- 文档、代码、告警规则必须同步提交
