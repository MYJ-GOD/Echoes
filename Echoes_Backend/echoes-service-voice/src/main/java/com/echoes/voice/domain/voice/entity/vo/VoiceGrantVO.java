package com.echoes.voice.domain.voice.entity.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 分享授权响应VO
 * 
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VoiceGrantVO {

    /**
     * 授权ID
     */
    private UUID grantId;

    /**
     * 音色资产ID
     */
    private UUID voiceAssetId;

    /**
     * 音色名称
     */
    private String voiceAssetName;

    /**
     * 授权者用户ID
     */
    private UUID grantorUserId;

    /**
     * 授权者昵称
     */
    private String grantorNickname;

    /**
     * 被授权者用户ID
     */
    private UUID granteeUserId;

    /**
     * 被授权者昵称
     */
    private String granteeNickname;

    /**
     * 权限: USE, MANAGE
     */
    private String permission;

    /**
     * 过期时间
     */
    private LocalDateTime expiresAt;

    /**
     * 授权创建时间
     */
    private LocalDateTime createTime;
}

