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
import java.util.UUID;

/**
 * 音色资产详情响应VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "音色资产详情")
public class VoiceAssetVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "音色资产ID")
    private UUID voiceAssetId;

    @Schema(description = "所有者用户ID")
    private UUID ownerUserId;

    @Schema(description = "音色名称")
    private String name;

    @Schema(description = "角色标签")
    private String role;

    @Schema(description = "角色标签描述")
    private String roleDesc;

    @Schema(description = "标签列表")
    private java.util.List<String> tags;

    @Schema(description = "状态: creating/ready/failed/deleted")
    private String status;

    @Schema(description = "状态描述")
    private String statusDesc;

    @Schema(description = "外部voiceId (用于对话)")
    private String voiceIdExternal;

    @Schema(description = "质量评分")
    private BigDecimal qualityScore;

    @Schema(description = "是否为默认音色")
    private Boolean isDefault;

    @Schema(description = "创建时间")
    private LocalDateTime createTime;

    @Schema(description = "更新时间")
    private LocalDateTime updateTime;

    @Schema(description = "最近训练任务ID")
    private UUID lastTrainingTaskId;

    @Schema(description = "最近训练状态")
    private String lastTrainingStatus;

    @Schema(description = "相似度评分")
    private BigDecimal similarityScore;

    @Schema(description = "声纹模型ID")
    private UUID voiceModelId;
}

