package com.echoes.admin.domain.governance.controller;

import com.echoes.admin.domain.governance.entity.vo.FailureOverviewVO;
import com.echoes.admin.domain.governance.service.ConversationMonitoringService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 对话链路监控 Controller
 */
@Slf4j
@Tag(name = "对话链路监控", description = "会话失败分析和 Turn 查询")
@RestController
@RequestMapping("/admin/conversation")
@RequiredArgsConstructor
public class ConversationController {

    private final ConversationMonitoringService monitoringService;

    /**
     * 失败总览
     */
    @GetMapping("/failures/overview")
    @Operation(summary = "失败分布总览")
    public FailureOverviewVO getFailuresOverview(
            @Parameter(description = "开始时间") @RequestParam(value = "timeFrom", required = false) String timeFrom,
            @Parameter(description = "结束时间") @RequestParam(value = "timeTo", required = false) String timeTo
    ) {
        return monitoringService.getFailuresOverview(timeFrom, timeTo);
    }

    /**
     * 查询 Turn 列表
     */
    @GetMapping("/turns")
    @Operation(summary = "查询 Turn 列表")
    public Map<String, Object> listTurns(
            @Parameter(description = "会话 ID") @RequestParam(value = "sessionId", required = false) String sessionId,
            @Parameter(description = "状态") @RequestParam(value = "status", required = false) String status,
            @Parameter(description = "错误码") @RequestParam(value = "errorCode", required = false) String errorCode,
            @Parameter(description = "页码") @RequestParam(value = "page", defaultValue = "1") Integer page,
            @Parameter(description = "每页数量") @RequestParam(value = "size", defaultValue = "20") Integer size
    ) {
        List<?> turns = monitoringService.listTurns(sessionId, status, errorCode, page, size);
        int total = monitoringService.countTurns(sessionId, status, errorCode);

        Map<String, Object> response = new HashMap<>();
        response.put("list", turns);
        response.put("total", total);
        response.put("page", page);
        response.put("size", size);
        return response;
    }

    /**
     * 根据 TurnId 查询详情
     */
    @GetMapping("/turns/{turnId}")
    @Operation(summary = "根据 TurnId 查询详情")
    public Map<String, Object> getTurn(
            @Parameter(description = "Turn ID", required = true) @PathVariable String turnId
    ) {
        return monitoringService.getTurnDetail(turnId);
    }

    /**
     * 幂等冲突统计
     */
    @GetMapping("/idempotency/conflicts")
    @Operation(summary = "幂等冲突统计")
    public Map<String, Object> getIdempotencyConflicts(
            @Parameter(description = "开始日期") @RequestParam(value = "dateFrom", required = false) String dateFrom,
            @Parameter(description = "结束日期") @RequestParam(value = "dateTo", required = false) String dateTo
    ) {
        return monitoringService.getIdempotencyConflicts(dateFrom, dateTo);
    }
}
