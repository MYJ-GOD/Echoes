package com.echoes.voice.domain.voice.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 训练任务详情响应VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "训练任务详情")
public class TrainingTaskVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "任务ID")
    private UUID taskId;

    @Schema(description = "音色资产ID")
    private UUID voiceAssetId;

    @Schema(description = "音色名称")
    private String voiceAssetName;

    @Schema(description = "声纹模型ID")
    private UUID voiceModelId;

    @Schema(description = "参考音频ID")
    private String refId;

    @Schema(description = "任务状态: pending/training/success/failed")
    private String status;

    @Schema(description = "状态描述")
    private String statusDesc;

    @Schema(description = "训练进度 (0-100)")
    private BigDecimal progress;

    @Schema(description = "进度百分比文本")
    private String progressText;

    @Schema(description = "日志路径")
    private String logPath;

    @Schema(description = "最近日志内容")
    private List<String> recentLogs;

    @Schema(description = "预计剩余时间")
    private String estimatedTimeRemaining;

    @Schema(description = "开始时间")
    private LocalDateTime startTime;

    @Schema(description = "结束时间")
    private LocalDateTime endTime;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

    @Schema(description = "相似度评分")
    private BigDecimal similarityScore;
}

