package com.echoes.admin.domain.governance.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Conversation Summary DTO（admin 本地类型，解耦 conversation jar 依赖）
 */
@Data
public class ConversationSummaryDTO {
    private UUID summaryId;
    private UUID conversationId;
    private String summary;
    private LocalDateTime createTime;
}
