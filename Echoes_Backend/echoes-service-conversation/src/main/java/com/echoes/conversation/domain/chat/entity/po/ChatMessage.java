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
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * AI对话消息实体
 * 符合"一闻如故"智能陪伴系统的存储场景
 * 支持语音合成、情感计算、向量检索等功能
 * 
 * @author echoes
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
@Document(collection = "echoes_chat_message")
@Schema(description = "AI对话消息")
public class ChatMessage extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    @Id
    @Schema(description = "消息ID")
    private UUID id;

    @Field("session_id")
    @Schema(description = "会话ID")
    private UUID sessionId;

    @Field("sys_user_id")
    @Schema(description = "用户ID，冗余字段，避免关联查询")
    private java.util.UUID sysUserId;

    @Field("parent_message_id")
    @Schema(description = "父消息ID，支持消息树结构")
    private UUID parentMessageId;

    @Field("message_index")
    @Schema(description = "消息序号，会话内顺序")
    private Integer messageIndex;

    @Field("role")
    @Schema(description = "角色: 0-用户, 1-AI助手, 2-系统")
    private Integer role;

    @Field("content")
    @Schema(description = "消息内容")
    private String content;

    @Field("message_type")
    @Schema(description = "消息类型: 0-文本, 1-代码, 2-图片, 3-文件, 4-语音")
    private Integer messageType;

    @Field("token_count")
    @Schema(description = "token数量")
    private Integer tokenCount;

    @Field("model_name")
    @Schema(description = "使用的模型名称")
    private String modelName;

    @Field("voice_id")
    @Schema(description = "使用的声纹模型ID，用于语音合成")
    private java.util.UUID voiceId;

    @Field("audio_url")
    @Schema(description = "语音合成后的音频URL（OSS存储）")
    private String audioUrl;

    @Field("emotion_tag")
    @Schema(description = "情感标记，用于情感计算和语音合成")
    private String emotionTag;

    @Field("vector_embedding")
    @Schema(description = "向量嵌入，用于语义搜索和个性化记忆")
    private List<Double> vectorEmbedding;

    @Field("references")
    @Schema(description = "引用的参考内容（RAG检索结果）")
    private List<Map<String, Object>> references;

    @Field("attachments")
    @Schema(description = "附件URL列表")
    private List<String> attachments;

    @Field("is_feedback")
    @Schema(description = "用户反馈: 0-无, 1-有用, -1-无用")
    private Integer isFeedback;

    @Field("is_deleted")
    @Schema(description = "逻辑删除标记: 0-否, 1-是")
    private Integer isDeleted;

    @Field("metadata")
    @Schema(description = "元数据，存储扩展信息")
    private Map<String, Object> metadata;
}

