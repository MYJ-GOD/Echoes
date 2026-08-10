package com.echoes.admin.domain.governance.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Voice Asset DTO（admin 本地类型，解耦 voice jar 依赖）
 */
@Data
public class VoiceAssetDTO {
    private UUID voiceAssetId;
    private UUID ownerUserId;
    private String name;
    private String role;
    private String status;
    private Double qualityScore;
    private String voiceIdExternal;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private Integer deleted;
}
