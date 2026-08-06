/*
 Navicat Premium Dump SQL

 Source Server         : Echoes
 Source Server Type    : MySQL
 Source Server Version : 80044 (8.0.44)
 Source Host           : localhost:3306
 Source Schema         : echoes

 Target Server Type    : MySQL
 Target Server Version : 80044 (8.0.44)
 File Encoding         : 65001

 Date: 22/02/2026 15:40:50
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for audio_asset
-- ----------------------------
DROP TABLE IF EXISTS `audio_asset`;
CREATE TABLE `audio_asset`  (
  `audio_ref` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `storage_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `format` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `duration_ms` int NULL DEFAULT NULL,
  `size_bytes` bigint NULL DEFAULT NULL,
  `sha256` binary(32) NULL DEFAULT NULL,
  `owner_user_id` binary(16) NOT NULL,
  `conversation_id` binary(16) NULL DEFAULT NULL,
  `turn_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `message_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`audio_ref`) USING BTREE,
  INDEX `idx_owner_time`(`owner_user_id` ASC, `deleted_at` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_conv_time`(`conversation_id` ASC, `deleted_at` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_turn`(`turn_id` ASC) USING BTREE,
  CONSTRAINT `fk_audio_conv` FOREIGN KEY (`conversation_id`) REFERENCES `conversation_session` (`conversation_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_audio_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Audio asset metadata & ownership mapping' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for content_favorite
-- ----------------------------
DROP TABLE IF EXISTS `content_favorite`;
CREATE TABLE `content_favorite`  (
  `id` binary(16) NOT NULL,
  `content_id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uniq_user_content`(`user_id` ASC, `content_id` ASC) USING BTREE,
  INDEX `idx_content`(`content_id` ASC, `create_time` ASC) USING BTREE,
  CONSTRAINT `fk_fav_content` FOREIGN KEY (`content_id`) REFERENCES `content_item` (`content_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_fav_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Content favorites' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for content_item
-- ----------------------------
DROP TABLE IF EXISTS `content_item`;
CREATE TABLE `content_item`  (
  `content_id` binary(16) NOT NULL,
  `owner_user_id` binary(16) NULL DEFAULT NULL COMMENT 'Nullable if system-provided',
  `type` enum('STORY','SOOTHING','REMINDER') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `summary` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `status` enum('READY','CREATING','FAILED','DELETED') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'READY',
  `metadata` json NULL,
  `body_storage_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Body stored in object storage (optional)',
  `audio_storage_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Pre-generated audio (optional)',
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`content_id`) USING BTREE,
  INDEX `idx_type_time`(`type` ASC, `deleted_at` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_owner_time`(`owner_user_id` ASC, `deleted_at` ASC, `create_time` ASC) USING BTREE,
  CONSTRAINT `fk_content_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Content library metadata' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for conversation_session
-- ----------------------------
DROP TABLE IF EXISTS `conversation_session`;
CREATE TABLE `conversation_session`  (
  `conversation_id` binary(16) NOT NULL COMMENT 'Conversation ID',
  `user_id` binary(16) NOT NULL COMMENT 'Owner user',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '新会话',
  `default_voice_asset_id` binary(16) NULL DEFAULT NULL COMMENT 'Default voice asset (optional)',
  `status` enum('active','archived') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'active',
  `last_message_time` datetime NULL DEFAULT NULL,
  `message_count` int NULL DEFAULT 0,
  `defaults` json NULL COMMENT 'Defaults in request (e.g., voiceId)',
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`conversation_id`) USING BTREE,
  INDEX `idx_user_time`(`user_id` ASC, `deleted_at` ASC, `last_message_time` ASC) USING BTREE,
  INDEX `idx_user_status`(`user_id` ASC, `status` ASC, `deleted_at` ASC) USING BTREE,
  CONSTRAINT `fk_conv_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Conversation sessions (authoritative list source)' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for conversation_summary
-- ----------------------------
DROP TABLE IF EXISTS `conversation_summary`;
CREATE TABLE `conversation_summary`  (
  `conversation_id` binary(16) NOT NULL,
  `total_input_tokens` bigint NULL DEFAULT 0,
  `total_output_tokens` bigint NULL DEFAULT 0,
  `avg_latency_ms` int NULL DEFAULT NULL,
  `last_turn_time` datetime NULL DEFAULT NULL,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`conversation_id`) USING BTREE,
  CONSTRAINT `fk_summary_conv` FOREIGN KEY (`conversation_id`) REFERENCES `conversation_session` (`conversation_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Conversation analytics aggregates' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for conversation_turn
-- ----------------------------
DROP TABLE IF EXISTS `conversation_turn`;
CREATE TABLE `conversation_turn`  (
  `id` binary(16) NOT NULL,
  `conversation_id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `turn_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Client-generated turn_id',
  `idempotency_key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Input-side idempotency key (default = turn_id)',
  `payload_hash` binary(32) NOT NULL COMMENT 'SHA-256 of canonical request payload used for mismatch detection',
  `status` enum('RUNNING','SUCCESS','FAILED','CANCELLED') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `final_message_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Mongo messageId (or external id) for final assistant message',
  `error_code` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `error_stage` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `retryable` tinyint NULL DEFAULT 0,
  `start_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `end_time` datetime NULL DEFAULT NULL,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uniq_conv_turn`(`conversation_id` ASC, `turn_id` ASC) USING BTREE,
  UNIQUE INDEX `uniq_conv_idempo`(`conversation_id` ASC, `idempotency_key` ASC) USING BTREE,
  INDEX `idx_user_time`(`user_id` ASC, `start_time` ASC) USING BTREE,
  INDEX `idx_status_time`(`status` ASC, `start_time` ASC) USING BTREE,
  CONSTRAINT `fk_turn_conv` FOREIGN KEY (`conversation_id`) REFERENCES `conversation_session` (`conversation_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_turn_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Authoritative turn state for REPLAY/ATTACH/409 decisions' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for core_user
-- ----------------------------
DROP TABLE IF EXISTS `core_user`;
CREATE TABLE `core_user`  (
  `user_id` binary(16) NOT NULL COMMENT 'User ID (UUID stored as 16 bytes)',
  `user_type` enum('elder','child','normal') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'normal' COMMENT 'User segment (for default mode strategy)',
  `name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Display name (NOT unique)',
  `phone_number` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Phone (optional)',
  `email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Email (optional)',
  `avatar_url` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Avatar URL',
  `status` enum('active','banned','inactive') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'active' COMMENT 'User status',
  `is_deleted` tinyint NULL DEFAULT 0 COMMENT 'Legacy soft-delete flag (avoid using in new code)',
  `deleted_at` datetime NULL DEFAULT NULL COMMENT 'Soft delete timestamp (preferred)',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created at',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated at',
  PRIMARY KEY (`user_id`) USING BTREE,
  UNIQUE INDEX `uniq_phone`(`phone_number` ASC) USING BTREE,
  UNIQUE INDEX `uniq_email`(`email` ASC) USING BTREE,
  INDEX `idx_user_type_status`(`user_type` ASC, `status` ASC, `deleted_at` ASC) USING BTREE,
  INDEX `idx_create_time`(`create_time` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Users' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for family
-- ----------------------------
DROP TABLE IF EXISTS `family`;
CREATE TABLE `family`  (
  `family_id` binary(16) NOT NULL,
  `owner_user_id` binary(16) NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`family_id`) USING BTREE,
  INDEX `idx_owner`(`owner_user_id` ASC, `deleted_at` ASC) USING BTREE,
  CONSTRAINT `fk_family_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Family' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for family_member
-- ----------------------------
DROP TABLE IF EXISTS `family_member`;
CREATE TABLE `family_member`  (
  `id` binary(16) NOT NULL,
  `family_id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `role` enum('PARENT','CHILD','CAREGIVER','OTHER') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uniq_family_user`(`family_id` ASC, `user_id` ASC) USING BTREE,
  INDEX `idx_user`(`user_id` ASC) USING BTREE,
  CONSTRAINT `fk_member_family` FOREIGN KEY (`family_id`) REFERENCES `family` (`family_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_member_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Family members' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for user_auth
-- ----------------------------
DROP TABLE IF EXISTS `user_auth`;
CREATE TABLE `user_auth`  (
  `auth_id` binary(16) NOT NULL COMMENT 'Auth record ID',
  `user_id` binary(16) NOT NULL,
  `provider` enum('WECHAT','APPLE','PHONE','EMAIL','OTHER') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `open_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Provider user identifier',
  `union_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Provider union identifier (if applicable)',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`auth_id`) USING BTREE,
  UNIQUE INDEX `uniq_provider_open`(`provider` ASC, `open_id` ASC) USING BTREE,
  INDEX `idx_user`(`user_id` ASC) USING BTREE,
  CONSTRAINT `fk_auth_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'User auth bindings' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for user_profile
-- ----------------------------
DROP TABLE IF EXISTS `user_profile`;
CREATE TABLE `user_profile`  (
  `user_id` binary(16) NOT NULL,
  `age_group` enum('CHILD','ADULT','ELDER') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `special_needs` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `default_mode` enum('DEFAULT','ELDER','CHILD','SPECIAL') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'DEFAULT',
  `preferences` json NULL COMMENT 'Strategy preferences (speech_rate, stimulation_level, etc.)',
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`) USING BTREE,
  CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'User profile for mode selection' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for user_voice_link
-- ----------------------------
DROP TABLE IF EXISTS `user_voice_link`;
CREATE TABLE `user_voice_link`  (
  `link_id` binary(16) NOT NULL,
  `user_id` binary(16) NOT NULL,
  `voice_asset_id` binary(16) NOT NULL,
  `nickname` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'User-friendly alias (e.g., 妈妈-温柔版)',
  `is_default` tinyint NULL DEFAULT 0,
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`link_id`) USING BTREE,
  UNIQUE INDEX `uniq_user_asset`(`user_id` ASC, `voice_asset_id` ASC) USING BTREE,
  INDEX `idx_user_default`(`user_id` ASC, `is_default` ASC, `deleted_at` ASC) USING BTREE,
  INDEX `fk_link_asset`(`voice_asset_id` ASC) USING BTREE,
  CONSTRAINT `fk_link_asset` FOREIGN KEY (`voice_asset_id`) REFERENCES `voice_asset` (`voice_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_link_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'User voice shortcuts/preferences (not grants)' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for voice_asset
-- ----------------------------
DROP TABLE IF EXISTS `voice_asset`;
CREATE TABLE `voice_asset`  (
  `voice_asset_id` binary(16) NOT NULL,
  `owner_user_id` binary(16) NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` enum('father','mother','friend','child','partner','self','other') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'other',
  `tags` json NULL,
  `status` enum('CREATING','READY','FAILED','DELETED') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `voice_id_external` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'voiceId usable in chat-stream overrides.voiceId',
  `quality_score` decimal(4, 2) NULL DEFAULT NULL,
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`voice_asset_id`) USING BTREE,
  INDEX `idx_owner_status`(`owner_user_id` ASC, `status` ASC, `deleted_at` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_owner_role`(`owner_user_id` ASC, `role` ASC, `deleted_at` ASC) USING BTREE,
  CONSTRAINT `fk_asset_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Product voice assets (authoritative for grants/audit)' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for voice_audit_log
-- ----------------------------
DROP TABLE IF EXISTS `voice_audit_log`;
CREATE TABLE `voice_audit_log`  (
  `audit_id` binary(16) NOT NULL,
  `voice_asset_id` binary(16) NOT NULL,
  `actor_user_id` binary(16) NOT NULL,
  `action` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `result` enum('ALLOWED','DENIED','ERROR') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `details` json NULL,
  `ts` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`audit_id`) USING BTREE,
  INDEX `idx_asset_ts`(`voice_asset_id` ASC, `ts` ASC) USING BTREE,
  INDEX `idx_actor_ts`(`actor_user_id` ASC, `ts` ASC) USING BTREE,
  CONSTRAINT `fk_audit_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_audit_asset` FOREIGN KEY (`voice_asset_id`) REFERENCES `voice_asset` (`voice_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Voice asset audit log' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for voice_grant
-- ----------------------------
DROP TABLE IF EXISTS `voice_grant`;
CREATE TABLE `voice_grant`  (
  `grant_id` binary(16) NOT NULL,
  `voice_asset_id` binary(16) NOT NULL,
  `grantee_user_id` binary(16) NOT NULL,
  `permission` enum('USE','MANAGE') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `expires_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`grant_id`) USING BTREE,
  UNIQUE INDEX `uniq_asset_grantee_perm`(`voice_asset_id` ASC, `grantee_user_id` ASC, `permission` ASC) USING BTREE,
  INDEX `idx_grantee`(`grantee_user_id` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_asset`(`voice_asset_id` ASC, `create_time` ASC) USING BTREE,
  CONSTRAINT `fk_grant_asset` FOREIGN KEY (`voice_asset_id`) REFERENCES `voice_asset` (`voice_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_grant_grantee` FOREIGN KEY (`grantee_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Voice asset grants (sharing/permissions)' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for voice_model
-- ----------------------------
DROP TABLE IF EXISTS `voice_model`;
CREATE TABLE `voice_model`  (
  `voice_model_id` binary(16) NOT NULL,
  `voice_asset_id` binary(16) NOT NULL,
  `ref_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_version` int NULL DEFAULT 1,
  `model_storage_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Model artifact path in object storage',
  `prompt` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `similarity_score` decimal(5, 3) NULL DEFAULT NULL,
  `status` enum('pending','training','success','failed') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'pending' COMMENT 'Training-layer status',
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`voice_model_id`) USING BTREE,
  UNIQUE INDEX `uniq_asset_version`(`voice_asset_id` ASC, `model_version` ASC) USING BTREE,
  INDEX `idx_ref`(`ref_id` ASC) USING BTREE,
  INDEX `idx_status_time`(`status` ASC, `create_time` ASC) USING BTREE,
  CONSTRAINT `fk_model_asset` FOREIGN KEY (`voice_asset_id`) REFERENCES `voice_asset` (`voice_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_model_ref` FOREIGN KEY (`ref_id`) REFERENCES `voice_ref` (`ref_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Training artifacts for a voice asset (can have multiple versions)' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for voice_ref
-- ----------------------------
DROP TABLE IF EXISTS `voice_ref`;
CREATE TABLE `voice_ref`  (
  `ref_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `owner_user_id` binary(16) NOT NULL,
  `conversation_id` binary(16) NULL DEFAULT NULL,
  `storage_key` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `format` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `duration_ms` int NULL DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ref_id`) USING BTREE,
  INDEX `idx_owner_exp`(`owner_user_id` ASC, `expires_at` ASC) USING BTREE,
  INDEX `idx_conv`(`conversation_id` ASC) USING BTREE,
  CONSTRAINT `fk_ref_conv` FOREIGN KEY (`conversation_id`) REFERENCES `conversation_session` (`conversation_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_ref_owner` FOREIGN KEY (`owner_user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Voice reference uploads (raw material, TTL enforced)' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for voice_training_task
-- ----------------------------
DROP TABLE IF EXISTS `voice_training_task`;
CREATE TABLE `voice_training_task`  (
  `task_id` binary(16) NOT NULL COMMENT 'Training task ID',
  `voice_asset_id` binary(16) NOT NULL,
  `voice_model_id` binary(16) NULL DEFAULT NULL,
  `ref_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` binary(16) NOT NULL,
  `status` enum('pending','training','success','failed') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'pending',
  `progress` decimal(5, 2) NULL DEFAULT 0.00,
  `log_path` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `start_time` datetime NULL DEFAULT NULL,
  `end_time` datetime NULL DEFAULT NULL,
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`task_id`) USING BTREE,
  INDEX `idx_user_status`(`user_id` ASC, `status` ASC) USING BTREE,
  INDEX `idx_asset_status`(`voice_asset_id` ASC, `status` ASC) USING BTREE,
  INDEX `idx_status_time`(`status` ASC, `start_time` ASC) USING BTREE,
  INDEX `fk_task_model`(`voice_model_id` ASC) USING BTREE,
  INDEX `fk_task_ref`(`ref_id` ASC) USING BTREE,
  CONSTRAINT `fk_task_asset` FOREIGN KEY (`voice_asset_id`) REFERENCES `voice_asset` (`voice_asset_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_task_model` FOREIGN KEY (`voice_model_id`) REFERENCES `voice_model` (`voice_model_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_task_ref` FOREIGN KEY (`ref_id`) REFERENCES `voice_ref` (`ref_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_task_user` FOREIGN KEY (`user_id`) REFERENCES `core_user` (`user_id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Voice training tasks (async job tracking)' ROW_FORMAT = Dynamic;

-- ==============================
-- RAG Knowledge Base Tables
-- For Phase 1: Knowledge Base Management
-- ==============================

-- ----------------------------
-- Table structure for knowledge_base
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_base`;
CREATE TABLE `knowledge_base`  (
  `kb_id` binary(16) NOT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `owner_user_id` binary(16) NULL DEFAULT NULL,
  `visibility` enum('PRIVATE','SHARED','PUBLIC') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'PRIVATE',
  `status` enum('ACTIVE','INDEXING','DISABLED') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'ACTIVE',
  `config` json NULL,
  `is_deleted` tinyint NULL DEFAULT 0,
  `deleted_at` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`kb_id`) USING BTREE,
  INDEX `idx_owner`(`owner_user_id` ASC, `deleted_at` ASC) USING BTREE,
  INDEX `idx_status`(`status` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'RAG Knowledge Base';

-- ----------------------------
-- Table structure for knowledge_document
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_document`;
CREATE TABLE `knowledge_document`  (
  `doc_id` binary(16) NOT NULL,
  `kb_id` binary(16) NOT NULL,
  `title` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type` enum('TEXT','MARKDOWN','PDF','URL') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'TEXT',
  `source_url` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `storage_key` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `word_count` int NULL DEFAULT NULL,
  `status` enum('PENDING','PROCESSING','READY','FAILED') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'PENDING',
  `metadata` json NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`doc_id`) USING BTREE,
  INDEX `idx_kb`(`kb_id` ASC, `status` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Knowledge Documents';

-- ----------------------------
-- Table structure for knowledge_chunk
-- ----------------------------
DROP TABLE IF EXISTS `knowledge_chunk`;
CREATE TABLE `knowledge_chunk`  (
  `chunk_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `doc_id` binary(16) NOT NULL,
  `kb_id` binary(16) NOT NULL,
  `chunk_index` int NOT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `embedding_version` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `vector_id` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Qdrant vector ID',
  `metadata` json NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`chunk_id`) USING BTREE,
  INDEX `idx_doc`(`doc_id` ASC, `chunk_index` ASC) USING BTREE,
  INDEX `idx_kb`(`kb_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Knowledge Chunks (for RAG retrieval)';

-- ----------------------------
-- Table structure for conversation_vector
-- ----------------------------
DROP TABLE IF EXISTS `conversation_vector`;
CREATE TABLE `conversation_vector`  (
  `vector_id` binary(16) NOT NULL,
  `conversation_id` binary(16) NOT NULL,
  `turn_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `vector_id_external` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT 'Qdrant vector ID',
  `embedding_model` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `message_type` enum('USER','ASSISTANT','SYSTEM') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'USER',
  `indexed` tinyint NULL DEFAULT 0 COMMENT 'Whether vectorized',
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`vector_id`) USING BTREE,
  INDEX `idx_conv`(`conversation_id` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_turn`(`turn_id` ASC) USING BTREE,
  INDEX `idx_indexed`(`indexed` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Conversation History Vectors (for semantic search)';

-- ----------------------------
-- Table structure for langgraph_workflow
-- ----------------------------
DROP TABLE IF EXISTS `langgraph_workflow`;
CREATE TABLE `langgraph_workflow`  (
  `workflow_id` binary(16) NOT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `owner_user_id` binary(16) NULL DEFAULT NULL,
  `graph_definition` json NOT NULL COMMENT 'Workflow graph definition',
  `nodes_config` json NULL,
  `variables` json NULL,
  `status` enum('ACTIVE','DRAFT','DISABLED') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'DRAFT',
  `version` int NULL DEFAULT 1,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`workflow_id`) USING BTREE,
  INDEX `idx_owner`(`owner_user_id` ASC, `status` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'LangGraph Workflow Definitions';

-- ----------------------------
-- Table structure for workflow_execution
-- ----------------------------
DROP TABLE IF EXISTS `workflow_execution`;
CREATE TABLE `workflow_execution`  (
  `execution_id` binary(16) NOT NULL,
  `workflow_id` binary(16) NOT NULL,
  `conversation_id` binary(16) NULL DEFAULT NULL,
  `turn_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('RUNNING','COMPLETED','FAILED','TIMEOUT') CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT 'RUNNING',
  `input_data` json NULL,
  `output_data` json NULL,
  `node_logs` json NULL,
  `error_message` varchar(1024) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `start_time` datetime NULL DEFAULT NULL,
  `end_time` datetime NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`execution_id`) USING BTREE,
  UNIQUE INDEX `idx_turn`(`turn_id` ASC) COMMENT 'Idempotency key',
  INDEX `idx_workflow`(`workflow_id` ASC, `create_time` ASC) USING BTREE,
  INDEX `idx_conv`(`conversation_id` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'Workflow Execution Records';

-- ----------------------------
-- Table structure for rag_retrieval_log
-- ----------------------------
DROP TABLE IF EXISTS `rag_retrieval_log`;
CREATE TABLE `rag_retrieval_log`  (
  `log_id` binary(16) NOT NULL,
  `turn_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `query_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `rewritten_query` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `intent_category` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `kb_ids` json NULL,
  `retrieved_count` int NULL DEFAULT NULL,
  `final_used_count` int NULL DEFAULT NULL,
  `rerank_enabled` tinyint NULL DEFAULT 0,
  `retrieval_latency_ms` int NULL DEFAULT NULL,
  `total_latency_ms` int NULL DEFAULT NULL,
  `success` tinyint NULL DEFAULT 1,
  `error_message` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `create_time` datetime NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`log_id`) USING BTREE,
  INDEX `idx_turn`(`turn_id` ASC) USING BTREE,
  INDEX `idx_time`(`create_time` ASC) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = 'RAG Retrieval Audit Log';

SET FOREIGN_KEY_CHECKS = 1;
