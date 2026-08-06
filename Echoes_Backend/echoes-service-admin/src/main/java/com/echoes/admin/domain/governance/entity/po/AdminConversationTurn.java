package com.echoes.admin.domain.governance.entity.po;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

@Data
public class AdminConversationTurn {
    private UUID id;
    private UUID conversationId;
    private UUID userId;
    private String turnId;
    private String idempotencyKey;
    private byte[] payloadHash;
    private String status;
    private String finalMessageId;
    private String errorCode;
    private String errorStage;
    private Integer retryable;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private LocalDateTime updateTime;
}
