package com.echoes.voice.domain.voice.mq;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 训练任务消息
 * 用于Redis Streams消息队列
 * 
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TrainingTaskMessage implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 消息ID (自动生成)
     */
    private String messageId;

    /**
     * 任务ID
     */
    private UUID taskId;

    /**
     * 音色资产ID
     */
    private UUID voiceAssetId;

    /**
     * 参考音频ID
     */
    private String refId;

    /**
     * OSS存储Key (用于Python消费者下载音频)
     */
    private String storageKey;

    /**
     * 用户ID
     */
    private UUID userId;

    /**
     * 模型版本号
     */
    private Integer modelVersion;

    /**
     * 自定义prompt
     */
    private String prompt;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 优先级 (1-10, 1最高)
     */
    private Integer priority;

    /**
     * 消息类型
     */
    private MessageType messageType;

    /**
     * 消息类型枚举
     */
    public enum MessageType {
        START_TRAINING,    // 开始训练
        CANCEL_TRAINING,   // 取消训练
        RETRY_TRAINING     // 重试训练
    }

    /**
     * 创建开始训练消息
     */
    public static TrainingTaskMessage createStartMessage(
            UUID taskId, UUID voiceAssetId, String refId, String storageKey,
            UUID userId, Integer modelVersion, String prompt) {
        return TrainingTaskMessage.builder()
                .messageId(UUID.randomUUID().toString())
                .taskId(taskId)
                .voiceAssetId(voiceAssetId)
                .refId(refId)
                .storageKey(storageKey)
                .userId(userId)
                .modelVersion(modelVersion != null ? modelVersion : 1)
                .prompt(prompt)
                .createTime(LocalDateTime.now())
                .priority(5)
                .messageType(MessageType.START_TRAINING)
                .build();
    }

    /**
     * 创建取消训练消息
     */
    public static TrainingTaskMessage createCancelMessage(UUID taskId, UUID voiceAssetId, UUID userId) {
        return TrainingTaskMessage.builder()
                .messageId(UUID.randomUUID().toString())
                .taskId(taskId)
                .voiceAssetId(voiceAssetId)
                .userId(userId)
                .createTime(LocalDateTime.now())
                .priority(1)  // 取消任务高优先级
                .messageType(MessageType.CANCEL_TRAINING)
                .build();
    }
}

