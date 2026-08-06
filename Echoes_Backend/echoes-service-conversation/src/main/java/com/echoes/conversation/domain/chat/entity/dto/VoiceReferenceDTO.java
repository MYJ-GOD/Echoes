package com.echoes.conversation.domain.chat.entity.dto;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

/**
 * 语音参考DTO
 * 用于存储语音克隆的参考音频信息
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class VoiceReferenceDTO {

    /**
     * 参考音频ID，由Echoes-AI生成
     */
    private String refId;

    /**
     * 参考文本，由Whisper自动转写或前端提供
     */
    private String refText;

    /**
     * 用户ID
     */
    private String userId;

    /**
     * 会话ID
     */
    private String sessionId;

    /**
     * 创建时间戳
     */
    private Long createdAt;

    /**
     * 过期时间戳（可选，用于清理）
     */
    private Long expiresAt;
}
