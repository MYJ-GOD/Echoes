package com.echoes.conversation.domain.chat.entity.po;

import com.echoes.conversation.common.converter.UUIDBytesConverter;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Turn 权威表 (MySQL v3)
 * 对应表: conversation_turn
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "conversation_turn")
public class ConversationTurn {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 主键 ID
     */
    @Id
    @Column(name = "id", columnDefinition = "BINARY(16)")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID id;

    @Column(name = "conversation_id", columnDefinition = "BINARY(16)")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID conversationId;

    @Column(name = "user_id", columnDefinition = "BINARY(16)")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID userId;

    /**
     * 客户端生成的 turn_id (字符串)
     */
    @Column(name = "turn_id", length = 64)
    private String turnId;

    @Column(name = "idempotency_key", length = 64)
    private String idempotencyKey;

    @Column(name = "payload_hash", columnDefinition = "BINARY(32)")
    private byte[] payloadHash;

    @Column(name = "status", length = 16)
    private String status;

    @Column(name = "final_message_id", length = 64)
    private String finalMessageId;

    @Column(name = "error_code", length = 64)
    private String errorCode;

    @Column(name = "error_stage", length = 32)
    private String errorStage;

    @Column(name = "retryable")
    private Integer retryable;

    @Column(name = "start_time")
    private LocalDateTime startTime;

    @Column(name = "end_time")
    private LocalDateTime endTime;

    @Column(name = "update_time")
    private LocalDateTime updateTime;
}
