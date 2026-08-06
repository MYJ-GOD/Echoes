package com.echoes.admin.domain.governance.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 时间线事件 VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "时间线事件")
public class TimelineEventVO {

    @Schema(description = "事件类型：SESSION_START/TURN_START/INFERENCE/AUDIT/TURN_END")
    private String eventType;

    @Schema(description = "事件时间")
    private LocalDateTime eventTime;

    @Schema(description = "事件描述")
    private String description;

    @Schema(description = "关联 ID (turnId/sessionId 等)")
    private String referenceId;

    @Schema(description = "状态：RUNNING/SUCCESS/FAILED")
    private String status;

    @Schema(description = "错误码（失败时）")
    private String errorCode;

    @Schema(description = "错误阶段（失败时）")
    private String errorStage;

    @Schema(description = "扩展数据")
    private Object data;
}
