package com.echoes.admin.domain.governance.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 时间线响应 VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "时间线响应")
public class TimelineResponseVO {

    @Schema(description = "会话 ID")
    private String sessionId;

    @Schema(description = "Turn ID")
    private String turnId;

    @Schema(description = "事件列表")
    private List<TimelineEventVO> events;
}
