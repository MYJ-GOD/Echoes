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
 * 会话统计摘要表 (MySQL v3)
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "conversation_summary")
public class ConversationSummary {

    @Serial
    private static final long serialVersionUID = 1L;

    @Id
    @Column(name = "conversation_id", columnDefinition = "BINARY(16)")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID conversationId;

    @Column(name = "total_input_tokens")
    private Long totalInputTokens;

    @Column(name = "total_output_tokens")
    private Long totalOutputTokens;

    @Column(name = "avg_latency_ms")
    private Integer avgLatencyMs;

    @Column(name = "last_turn_time")
    private LocalDateTime lastTurnTime;

    @Column(name = "update_time")
    private LocalDateTime updateTime;
}
