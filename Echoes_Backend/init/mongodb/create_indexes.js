/**
 * MongoDB索引创建脚本
 * 用于优化ChatSession和ChatMessage集合的查询性能
 * 
 * 执行方式：
 * mongo <database_name> create_indexes.js
 * 或
 * mongosh <database_name> create_indexes.js
 */

// 切换到目标数据库（如果使用mongosh，需要在命令行指定数据库）
// use echoes;

print("开始创建MongoDB索引...");

// ==================== ChatSession 集合索引 ====================
print("\n创建 echoes_chat_session 集合索引...");

// 1. 用户ID + 归档状态 + 最后消息时间（用于查询用户会话列表，按时间排序）
db.echoes_chat_session.createIndex(
  { "sys_user_id": 1, "is_archived": 1, "last_message_time": -1 },
  { name: "idx_user_archived_time" }
);
print("✓ 创建索引: idx_user_archived_time");

// 2. 用户ID + 置顶状态 + 更新时间（用于查询用户会话列表，置顶优先）
db.echoes_chat_session.createIndex(
  { "sys_user_id": 1, "is_pinned": -1, "update_time": -1 },
  { name: "idx_user_pinned_update" }
);
print("✓ 创建索引: idx_user_pinned_update");

// 3. 声纹ID（用于查询特定声纹的会话）
db.echoes_chat_session.createIndex(
  { "voice_id": 1 },
  { name: "idx_voice_id",
    partialFilterExpression: { "voice_id": { $exists: true, $ne: null } }
  }
);
print("✓ 创建索引: idx_voice_id");

// 4. 会话ID（主键索引，MongoDB自动创建，这里仅作说明）
// _id 索引已自动创建

print("\n✓ echoes_chat_session 集合索引创建完成");

// ==================== ChatMessage 集合索引 ====================
print("\n创建 echoes_chat_message 集合索引...");

// 1. 会话ID + 消息序号（用于按顺序查询会话消息）
db.echoes_chat_message.createIndex(
  { "session_id": 1, "message_index": 1 },
  { name: "idx_session_index" }
);
print("✓ 创建索引: idx_session_index");

// 2. 会话ID + 创建时间（用于查询最后一条消息）
db.echoes_chat_message.createIndex(
  { "session_id": 1, "create_time": -1 },
  { name: "idx_session_createtime" }
);
print("✓ 创建索引: idx_session_createtime");

// 3. 用户ID + 创建时间（用于查询用户的所有消息）
db.echoes_chat_message.createIndex(
  { "sys_user_id": 1, "create_time": -1 },
  { name: "idx_user_createtime",
    partialFilterExpression: { "sys_user_id": { $exists: true, $ne: null } }
  }
);
print("✓ 创建索引: idx_user_createtime");

// 4. 父消息ID（用于查询消息树结构）
db.echoes_chat_message.createIndex(
  { "parent_message_id": 1 },
  { name: "idx_parent_message",
    partialFilterExpression: { "parent_message_id": { $exists: true, $ne: null } }
  }
);
print("✓ 创建索引: idx_parent_message");

// 5. 逻辑删除标记（用于过滤已删除消息）
db.echoes_chat_message.createIndex(
  { "is_deleted": 1 },
  { name: "idx_is_deleted" }
);
print("✓ 创建索引: idx_is_deleted");

// 6. 消息ID（主键索引，MongoDB自动创建）
// _id 索引已自动创建

print("\n✓ echoes_chat_message 集合索引创建完成");

// ==================== 索引信息查询 ====================
print("\n" + "=".repeat(50));
print("索引创建完成！");
print("=".repeat(50));

print("\n当前 echoes_chat_session 集合索引：");
db.echoes_chat_session.getIndexes().forEach(function(index) {
  print("  - " + index.name + ": " + JSON.stringify(index.key));
});

print("\n当前 echoes_chat_message 集合索引：");
db.echoes_chat_message.getIndexes().forEach(function(index) {
  print("  - " + index.name + ": " + JSON.stringify(index.key));
});

print("\n脚本执行完成！");

