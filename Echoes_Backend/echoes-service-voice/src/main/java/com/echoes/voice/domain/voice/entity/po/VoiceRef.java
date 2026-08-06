package com.echoes.voice.domain.voice.entity.po;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 原始音频引用表 - 训练素材
 * 对应表: voice_ref
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VoiceRef {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 引用ID (String类型，对应SQL的VARCHAR(64))
     */
    private String refId;

    /**
     * 所有者用户ID
     */
    private UUID ownerUserId;

    /**
     * 关联的会话ID (可选)
     */
    private UUID conversationId;

    /**
     * OSS存储Key (用于训练时下载音频)
     */
    private String storageKey;

    /**
     * 音频格式: wav/mp3
     */
    private String format;

    /**
     * 音频时长(毫秒)
     */
    private Integer durationMs;

    /**
     * 过期时间
     */
    private LocalDateTime expiresAt;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}

