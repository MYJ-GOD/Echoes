package com.echoes.conversation.domain.chat.entity.po;

import com.echoes.entity.BaseEntity;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.io.Serial;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * AI对话会话实体
 * 符合"一闻如故"智能陪伴系统的存储场景
 * 
 * @author echoes
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@Document(collection = "echoes_chat_session")
@Schema(description = "AI对话会话")
public class ChatSession extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    @Id
    @Schema(description = "会话ID")
    private UUID id;

    @Field("sys_user_id")
    @Schema(description = "用户ID")
    private java.util.UUID sysUserId;

    @Field("voice_id")
    @Schema(description = "声纹模型ID，关联用户的声音模型")
    private java.util.UUID voiceId;

    @Field("session_title")
    @Schema(description = "会话标题")
    private String sessionTitle;

    @Field("session_type")
    @Schema(description = "会话类型: 0-普通对话, 1-课程问答, 2-题目辅导, 3-知识检索")
    private Integer sessionType;

    @Field("model_name")
    @Schema(description = "使用的大模型名称，如: qwen3-max")
    private String modelName;

    @Field("temperature")
    @Schema(description = "温度参数，控制生成文本的随机性")
    private BigDecimal temperature;

    @Field("top_p")
    @Schema(description = "Top-p 采样参数，控制生成文本的多样性")
    private BigDecimal topP;

    @Field("max_tokens")
    @Schema(description = "最大token数量")
    private Integer maxTokens;

    @Field("talk_speed")
    @Schema(description = "语速调节参数")
    private BigDecimal talkSpeed;

    @Field("is_pinned")
    @Schema(description = "是否置顶: 0-否, 1-是")
    private Integer isPinned;

    @Field("is_favorite")
    @Schema(description = "是否收藏: 0-否, 1-是")
    private Integer isFavorite;

    @Field("is_archived")
    @Schema(description = "是否归档: 0-否, 1-是")
    private Integer isArchived;

    @Field("last_message_id")
    @Schema(description = "最后一条消息ID，减少关联查询")
    private UUID lastMessageId;

    @Field("last_message_time")
    @Schema(description = "最后消息时间，用于排序和统计")
    private LocalDateTime lastMessageTime;

    @Field("message_count")
    @Schema(description = "消息总数，减少聚合查询")
    private Long messageCount;

    @Field("total_tokens")
    @Schema(description = "总token数，用于成本统计")
    private Long totalTokens;

    @Field("summary")
    @Schema(description = "会话摘要，用于快速了解对话内容")
    private String summary;
}

