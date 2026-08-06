package com.echoes.admin.domain.governance.controller;

import com.echoes.admin.domain.governance.entity.dto.AuditQueryDTO;
import com.echoes.admin.domain.governance.entity.vo.AuditEventVO;
import com.echoes.admin.domain.governance.entity.vo.TimelineResponseVO;
import com.echoes.admin.domain.governance.service.AuditEventService;
import com.echoes.admin.domain.governance.service.TimelineService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 审计检索 Controller
 */
@Slf4j
@Tag(name = "审计检索", description = "审计事件查询和时间线聚合")
@RestController
@RequestMapping("/admin/audit")
@RequiredArgsConstructor
public class AuditController {

    private final AuditEventService auditEventService;
    private final TimelineService timelineService;

    /**
     * 分页查询审计事件
     */
    @GetMapping("/events")
    @Operation(summary = "分页查询审计事件")
    public Map<String, Object> listAuditEvents(
            @Parameter(description = "Trace ID") @RequestParam(value = "traceId", required = false) String traceId,
            @Parameter(description = "Session ID") @RequestParam(value = "sessionId", required = false) String sessionId,
            @Parameter(description = "Turn ID") @RequestParam(value = "turnId", required = false) String turnId,
            @Parameter(description = "用户 ID") @RequestParam(value = "userId", required = false) String userId,
            @Parameter(description = "音色资产 ID") @RequestParam(value = "voiceAssetId", required = false) String voiceAssetId,
            @Parameter(description = "操作类型") @RequestParam(value = "action", required = false) String action,
            @Parameter(description = "操作结果") @RequestParam(value = "result", required = false) String result,
            @Parameter(description = "开始时间") @RequestParam(value = "timeFrom", required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime timeFrom,
            @Parameter(description = "结束时间") @RequestParam(value = "timeTo", required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime timeTo,
            @Parameter(description = "页码") @RequestParam(value = "page", defaultValue = "1") Integer page,
            @Parameter(description = "每页数量") @RequestParam(value = "size", defaultValue = "20") Integer size
    ) {
        AuditQueryDTO query = AuditQueryDTO.builder()
                .traceId(traceId)
                .sessionId(sessionId)
                .turnId(turnId)
                .userId(userId)
                .voiceAssetId(voiceAssetId)
                .action(action)
                .result(result)
                .timeFrom(timeFrom)
                .timeTo(timeTo)
                .page(page)
                .size(size)
                .build();

        List<AuditEventVO> events = auditEventService.listAuditEvents(query);
        int total = auditEventService.countAuditEvents(query);

        Map<String, Object> response = new HashMap<>();
        response.put("list", events);
        response.put("total", total);
        response.put("page", page);
        response.put("size", size);
        return response;
    }

    /**
     * 根据 ID 查询审计事件
     */
    @GetMapping("/events/{eventId}")
    @Operation(summary = "根据 ID 查询审计事件")
    public AuditEventVO getAuditEvent(
            @Parameter(description = "审计事件 ID") @PathVariable String eventId
    ) {
        return auditEventService.getAuditEventById(eventId);
    }

    /**
     * 获取时间线
     */
    @GetMapping("/timeline")
    @Operation(summary = "获取时间线（按 turnId）")
    public TimelineResponseVO getTimeline(
            @Parameter(description = "Turn ID", required = true) @RequestParam("turnId") String turnId
    ) {
        return timelineService.getTimelineByTurnId(turnId);
    }
}
