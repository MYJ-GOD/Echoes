package com.echoes.admin.domain.governance.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Conversation Turn DTO（admin 本地类型，解耦 conversation jar 依赖）
 */
@Data
public class ConversationTurnDTO {
    private Long id;
    private String turnId;
    private UUID conversationId;
    private String userMessage;
    private String assistantMessage;
    private LocalDateTime createTime;
}
