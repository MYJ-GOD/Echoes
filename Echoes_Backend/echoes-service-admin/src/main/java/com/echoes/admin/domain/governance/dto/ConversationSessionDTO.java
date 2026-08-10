package com.echoes.admin.domain.governance.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Conversation Session DTO（admin 本地类型，解耦 conversation jar 依赖）
 */
@Data
public class ConversationSessionDTO {
    private UUID conversationId;
    private UUID userId;
    private String sessionTitle;
    private String status;
    private UUID defaultVoiceAssetId;
    private LocalDateTime lastMessageTime;
    private Integer messageCount;
    private Integer isDeleted;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
