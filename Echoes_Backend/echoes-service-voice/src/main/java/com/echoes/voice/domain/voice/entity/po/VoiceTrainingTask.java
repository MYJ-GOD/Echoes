package com.echoes.voice.domain.voice.entity.po;

import com.echoes.entity.BaseEntity;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 声纹模型训练任务表
 * 对应表: voice_training_task
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class VoiceTrainingTask extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 任务ID
     */
    private UUID taskId;

    /**
     * 音色资产ID
     */
    private UUID voiceAssetId;

    /**
     * 声纹模型ID (训练完成后填充)
     */
    private UUID voiceModelId;

    /**
     * 参考音频ID
     */
    private String refId;

    /**
     * 用户ID
     */
    private UUID userId;

    /**
     * 任务状态: pending/training/success/failed
     */
    private String status;

    /**
     * 训练进度百分比 (0-100)
     */
    private BigDecimal progress;

    /**
     * 重试次数
     */
    private Integer retryCount;

    /**
     * 模型版本号
     */
    private Integer modelVersion;

    /**
     * 自定义prompt
     */
    private String prompt;

    /**
     * 日志文件路径
     */
    private String logPath;

    /**
     * 开始时间
     */
    private LocalDateTime startTime;

    /**
     * 结束时间
     */
    private LocalDateTime endTime;

    /**
     * 是否删除
     */
    private Integer deleted;

    /**
     * 删除时间
     */
    private LocalDateTime deletedAt;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
}
