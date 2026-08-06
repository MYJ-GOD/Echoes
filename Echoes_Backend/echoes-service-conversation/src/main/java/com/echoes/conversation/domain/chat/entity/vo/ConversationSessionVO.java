package com.echoes.conversation.domain.chat.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * MySQL 会话表 conversation_session 的 VO
 * 结构尽量与前端现有使用保持一致（包含 id 和 sessionTitle 等字段）
 */
@Data
@Schema(description = "联系人会话（MySQL）")
public class ConversationSessionVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "会话ID（conversation_id）")
    private String id;

    @Schema(description = "用户ID")
    private String userId;

    @Schema(description = "音色资产ID（voice_asset_id）")
    private String voiceAssetId;

    @Schema(description = "会话标题")
    private String sessionTitle;

    @Schema(description = "会话状态")
    private String status;

    @Schema(description = "最后消息时间")
    private LocalDateTime lastMessageTime;

    @Schema(description = "消息总数")
    private Integer messageCount;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    private LocalDateTime updateTime;
    
    @Schema(description = "关联的 ChatSessionId (UUID)，如果后端同时创建了 Mongo ChatSession 则返回此字段")
    private String chatSessionId;
}


