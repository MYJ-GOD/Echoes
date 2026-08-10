package com.echoes.admin.domain.governance.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Voice Model DTO（admin 本地类型，解耦 voice jar 依赖）
 */
@Data
public class VoiceModelDTO {
    private UUID voiceModelId;
    private UUID voiceAssetId;
    private String modelVersion;
    private Double similarityScore;
    private String status;
    private LocalDateTime createTime;
}
