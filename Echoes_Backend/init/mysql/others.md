1️⃣ Redis 使用规范（In-flight / Streaming 专用）
1.1 Redis 定位（写死）

Redis 仅用于短生命周期、可丢失的热状态，包括：

进行中的 turn 状态

SSE 流式事件缓冲（续播）

attach / resume / cancel 控制

限流 / 防抖

Redis 不是权威数据源，任何 Redis 数据丢失：

不得影响幂等裁决

不得影响历史消息正确性

必须能通过 MySQL + Mongo 恢复或返回协议级错误

1.2 Key 设计规范（强约束）
1️⃣ turn 状态（必需）
turn:{conversationId}:{turnId}


类型：HASH

字段：

字段	含义
state	RUNNING / CANCELLED
last_seq	已发送的最大 seq
updated_at	最近更新时间

TTL：24h ~ 7d（与 turn_event_log 一致）

2️⃣ SSE 事件缓冲（必需）
turnlog:{conversationId}:{turnId}


类型：LIST 或 STREAM

内容：

{
  "seq": 12,
  "type": "message.delta | audio.chunk | error | end",
  "data": {...},
  "ts": "ISO-8601"
}


约束：

必须按 seq 严格递增写入

只用于 resume_from_seq 补发

TTL 到期即不可续播（返回 410）

3️⃣ 幂等快速挡板（可选但推荐）
idempo:{conversationId}:{turnId}


用于高并发下减少 MySQL 压力

只作缓存，不可替代 MySQL 裁决

4️⃣ 限流（推荐）
rl:{userId}:{minute}


用于 voice-ref 上传、chat-stream 防刷

达到阈值直接返回 RATE_LIMITED

1.3 Redis 红线（严禁）

❌ Redis 中 不得存储：

最终态 message

payload_hash / 幂等裁决依据

会话聚合字段

任何需要长期留存的数据

2️⃣ MongoDB 使用规范（最终态 Message 专用）
2.1 MongoDB 定位（写死）

MongoDB 仅用于存储最终态聊天消息。

一条 message = 一条文档

仅在 turn 完成后写入

不参与流式、不参与幂等裁决、不参与会话聚合

2.2 Collection 规范
messages

示例文档：

{
  "messageId": "m_xxx",
  "conversationId": "c_xxx",
  "turn_id": "turn_xxx",
  "role": "user | assistant",
  "content": "你好",
  "audio_ref": "audio_123",
  "voiceId_used": "voice_va_123",
  "mode": "CHILD",
  "createdAt": "2026-01-09T10:00:01Z",
  "deleted_at": null
}

2.3 索引（必须）
db.messages.createIndex({ conversationId: 1, createdAt: 1 })
db.messages.createIndex({ messageId: 1 }, { unique: true })
db.messages.createIndex({ turn_id: 1 })

2.4 MongoDB 红线（严禁）

❌ MongoDB 不得存储：

streaming / delta / audio.chunk

turn 进行中状态

seq / resume / attach

会话统计字段（message_count / last_message_time）

幂等裁决信息

3️⃣ Kafka / MQ 使用规范（异步任务专用）
3.1 Kafka 定位（写死）

Kafka（或等价 MQ）用于：

voice-asset 建模

chat / TTS 执行（长文本 / 高并发）

数据导出

异步清理

审计 / 埋点（可选）

Kafka 不参与：

SSE 顺序控制

seq 生成

对外协议输出

3.2 Topic 规范（推荐最小集）
Topic	用途
job.voice_asset.train	声纹训练
job.chat.execute	对话/TTS 执行
job.user.export	数据导出
job.cleanup	异步清理
3.3 Kafka 强约束（必须）

1️⃣ 事件 key 必须使用 turn_id

保证同一 turn 内事件有序

减少 Java 侧重排复杂度

2️⃣ Kafka 事件不得携带 seq

seq 永远由 Java 生成

Kafka 只携带业务事件与 chunk_index

3️⃣ 消费必须幂等

同一事件可能被重复消费

Java / Worker 必须能安全去重

4️⃣ 对象存储使用规范（大文件专用）
4.1 对象存储定位

对象存储用于：

voice-ref 原始音频

声纹模型文件

对话生成音频

data-export 压缩包

数据库 仅存储引用（storage_key）。

4.2 命名规范（推荐）
voice-ref/{userId}/{refId}.wav
voice-model/{voiceAssetId}/{version}/model.bin
audio/{conversationId}/{messageId}.wav
export/{userId}/{exportId}.zip

4.3 访问规范（写死）

对外访问一律通过：

GET /conversation/audio/{audio_ref}


返回 302 或临时签名 URL

权限校验 必须在 MySQL 完成

5️⃣ 跨中间件一致性原则（必须遵守）
5.1 权威顺序（写死）
MySQL（权威裁决）
  ↓
Redis（热态 / 续播）
  ↓
MongoDB（最终消息）
  ↓
对象存储（大文件）


幂等 / 权限 / 状态 → MySQL

in-flight / streaming → Redis

历史消息 → Mongo

大文件 → 对象存储

5.2 end.status = SUCCESS 前置条件（再次强调）

以下条件未满足，严禁发送 SUCCESS：

Mongo 最终 message 未写入成功

MySQL turn 未进入 SUCCESS

会话聚合未更新或进入最终一致流程

6️⃣ 常见违规清单（Code Review 红线）

❌ 在 Redis 存最终消息
❌ 在 Mongo 存 streaming/delta
❌ Kafka 决定 seq
❌ 依赖 Redis 判断 turn 是否存在
❌ Mongo 做会话列表排序
❌ 对象存储绕过 /conversation/audio/{audio_ref} 直链给前端

架构兜底声明（中间件层）

Echoes 只承诺 用户感知上的 exactly-once。

任何中间件的 数据丢失、重试、重复消费，
不得破坏：

Java 单一出口

SSE 单一入口

seq 单点生成

turn_id 权威裁决模型