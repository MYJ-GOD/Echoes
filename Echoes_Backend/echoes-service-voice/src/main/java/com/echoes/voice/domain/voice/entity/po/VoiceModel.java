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
 * 声纹模型表
 * 对应表: voice_model
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class VoiceModel extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 声纹模型ID
     */
    private UUID voiceModelId;

    /**
     * 关联音色资产ID
     */
    private UUID voiceAssetId;

    /**
     * 参考音频 refId
     */
    private String refId;

    /**
     * 模型版本号
     */
    private Integer modelVersion;

    /**
     * 模型文件对象存储路径
     */
    private String modelStorageKey;

    /**
     * 训练 prompt
     */
    private String prompt;

    /**
     * 相似度评分
     */
    private BigDecimal similarityScore;

    /**
     * 训练状态: pending/training/success/failed
     */
    private String status;

    /**
     * 删除时间
     */
    private LocalDateTime deletedAt;
}
