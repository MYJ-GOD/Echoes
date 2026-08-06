package com.echoes.admin.domain.governance.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.UUID;

/**
 * 审计事件 VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "审计事件")
public class AuditEventVO {

    @Schema(description = "审计 ID")
    private UUID auditId;

    @Schema(description = "音色资产 ID")
    private UUID voiceAssetId;

    @Schema(description = "操作用户 ID")
    private UUID actorUserId;

    @Schema(description = "操作类型")
    private String action;

    @Schema(description = "操作结果")
    private String result;

    @Schema(description = "操作详情 (JSON)")
    private String details;

    @Schema(description = "操作时间")
    private LocalDateTime ts;

    @Schema(description = "扩展字段")
    private Map<String, Object> extendedFields;
}
