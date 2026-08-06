package com.echoes.voice.domain.voice.entity.po;

import com.echoes.entity.BaseEntity;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 音色授权表 - 分享/权限管理
 * 对应表: voice_grant
 * 
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class VoiceGrant extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 授权ID
     */
    private UUID grantId;

    /**
     * 授权者用户ID（分享人）
     */
    private UUID grantorUserId;

    /**
     * 音色资产ID
     */
    private UUID voiceAssetId;

    /**
     * 被授权用户ID
     */
    private UUID granteeUserId;

    /**
     * 权限: USE/MANAGE
     */
    private String permission;

    /**
     * 过期时间 (可选)
     */
    private LocalDateTime expiresAt;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}

