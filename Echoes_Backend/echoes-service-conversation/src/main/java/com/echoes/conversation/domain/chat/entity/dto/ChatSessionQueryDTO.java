package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;
import lombok.EqualsAndHashCode;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import com.echoes.conversation.domain.chat.enums.SessionStatus;

/**
 * 聊天会话查询DTO
 */
@Data
@EqualsAndHashCode
@Schema(description = "聊天会话查询数据传输对象")
public class ChatSessionQueryDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "页码，从1开始")
    private Integer pageNum = 1;

    @Schema(description = "每页数量")
    private Integer pageSize = 10;

    @Schema(description = "用户ID")
    private String sysUserId;

    @Schema(description = "会话标题（模糊查询）")
    private String sessionTitle;
    // Fields aligned with `conversation_session` table and common query needs:
    @Schema(description = "关联的声纹模型ID (voice_id)")
    private String voiceId;

    @Schema(description = "使用的大模型名称，用于筛选 (model_name)")
    private String modelName;

    @Schema(description = "会话状态枚举：ACTIVE/ENDED/ERROR")
    private SessionStatus status;

    @Schema(description = "最后消息时间 - 开始范围（用于时间区间筛选）")
    private LocalDateTime lastMessageTimeStart;

    @Schema(description = "最后消息时间 - 结束范围（用于时间区间筛选）")
    private LocalDateTime lastMessageTimeEnd;

    @Schema(description = "最小消息数（用于筛选活跃会话）")
    private Integer minMessageCount;

    @Schema(description = "排序字段，例如: last_message_time / start_time / message_count")
    private String sortBy;
}

