package com.echoes.conversation.domain.chat.entity.po;

import com.echoes.conversation.domain.chat.converter.SessionStatusConverter;
import com.echoes.conversation.domain.chat.enums.SessionStatus;
import jakarta.persistence.*;
import com.echoes.conversation.common.converter.UUIDBytesConverter;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import jakarta.persistence.Transient;
import java.util.UUID;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

/**
 * 会话表（MySQL版本）
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "conversation_session")
@JsonIgnoreProperties(ignoreUnknown = true)
public class ConversationSession {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 会话ID（UUID）
     */
    @Id
    @Column(name = "conversation_id", columnDefinition = "BINARY(16)")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID conversationId;

    /**
     * 用户ID
     */
    @Column(name = "user_id")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID userId;

    /**
     * 默认声纹资产ID（voice_asset_id）
     */
    @Column(name = "default_voice_asset_id")
    @Convert(converter = UUIDBytesConverter.class)
    private UUID defaultVoiceAssetId;

    /**
     * 会话标题
     */
    @Column(name = "title")
    private String sessionTitle;

    /**
     * 最后消息时间
     */
    @Column(name = "last_message_time")
    private LocalDateTime lastMessageTime;

    @Column(name = "message_count")
    private Integer messageCount;

    @Column(name = "defaults", columnDefinition = "json")
    private String defaults;

    @Column(name = "is_deleted")
    private Integer isDeleted;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

    @Column(name = "create_time")
    private LocalDateTime createTime;

    @Column(name = "update_time")
    private LocalDateTime updateTime;

    /**
     * 会话摘要（兼容旧代码，MySQL v3 使用 `defaults`/其他聚合字段，故标为 transient）
     */
    @Transient
    private String summary;

    /**
     * 会话状态
     * 使用自定义转换器，将数据库中的小写字符串（如 "active"）转换为枚举（如 SessionStatus.ACTIVE）
     */
    @Convert(converter = SessionStatusConverter.class)
    @Column(name = "status")
    private SessionStatus status;

    
}

