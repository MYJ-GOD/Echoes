package com.echoes.admin.domain.governance.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 审计事件查询 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "审计事件查询条件")
public class AuditQueryDTO {

    @Schema(description = "Trace ID")
    private String traceId;

    @Schema(description = "Session ID")
    private String sessionId;

    @Schema(description = "Turn ID")
    private String turnId;

    @Schema(description = "用户 ID")
    private String userId;

    @Schema(description = "音色资产 ID")
    private String voiceAssetId;

    @Schema(description = "操作类型")
    private String action;

    @Schema(description = "操作结果")
    private String result;

    @Schema(description = "开始时间")
    private LocalDateTime timeFrom;

    @Schema(description = "结束时间")
    private LocalDateTime timeTo;

    @Schema(description = "页码", defaultValue = "1")
    private Integer page = 1;

    @Schema(description = "每页数量", defaultValue = "20")
    private Integer size = 20;
}
