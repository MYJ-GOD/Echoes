package com.echoes.admin.domain.governance.dto;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Voice Training Task DTO（admin 本地类型，解耦 voice jar 依赖）
 */
@Data
public class VoiceTrainingTaskDTO {
    private UUID taskId;
    private UUID voiceAssetId;
    private String refId;
    private UUID userId;
    private String status;
    private Integer progress;
    private String logPath;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
}
