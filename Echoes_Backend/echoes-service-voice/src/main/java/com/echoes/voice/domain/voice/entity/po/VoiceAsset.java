package com.echoes.voice.domain.voice.entity.po;

import com.echoes.voice.domain.voice.enums.AssetStatus;
import com.echoes.voice.domain.voice.enums.VoiceRole;
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
 * 音色资产表实体
 * 对应表: voice_asset
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VoiceAsset implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 音色资产ID
     */
    private UUID voiceAssetId;

    /**
     * 所有者用户ID
     */
    private UUID ownerUserId;

    /**
     * 音色名称
     */
    private String name;

    /**
     * 角色：father/mother/friend/child/partner/self/other
     */
    private VoiceRole role;

    /**
     * 标签（JSON格式）
     */
    private String tags;

    /**
     * 状态：creating/ready/failed
     */
    private AssetStatus status;

    /**
     * 外部voiceId（用于对接第三方TTS服务）
     */
    private String voiceIdExternal;

    /**
     * 质量评分（0-100）
     */
    private BigDecimal qualityScore;

    /**
     * 是否已删除
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

