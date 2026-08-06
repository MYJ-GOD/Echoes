package com.echoes.admin.domain.governance.service;

import com.echoes.admin.domain.governance.entity.vo.FailureOverviewVO;
import com.echoes.admin.domain.governance.entity.po.AdminConversationTurn;
import com.echoes.admin.domain.governance.repository.AdminConversationTurnMapper;
import com.echoes.admin.domain.governance.repository.AdminConversationTurnMapper.FailureStatistics;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 对话监控服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ConversationMonitoringService {

    private final AdminConversationTurnMapper turnMapper;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String IDEMPOTENCY_CONFLICT_METRIC_KEY_PREFIX = "metrics:conversation:idempotency_conflict:";

    /**
     * 获取失败总览
     */
    public FailureOverviewVO getFailuresOverview(String timeFrom, String timeTo) {
        LocalDateTime from = parseDate(timeFrom);
        LocalDateTime to = parseDate(timeTo);

        int totalTurns = turnMapper.countTotalTurns();
        List<FailureStatistics> stats = turnMapper.selectFailureStatistics(from, to);

        int failedTurns = stats.stream().mapToInt(FailureStatistics::getCount).sum();
        double failureRate = totalTurns > 0 ? (double) failedTurns / totalTurns : 0.0;

        // 按错误码分组
        List<FailureOverviewVO.ErrorCodeStatistics> errorCodeStats = stats.stream()
                .map(s -> FailureOverviewVO.ErrorCodeStatistics.builder()
                        .errorCode(s.getErrorCode())
                        .errorStage(s.getErrorStage())
                        .count(s.getCount())
                        .percentage(failedTurns > 0 ? (double) s.getCount() / failedTurns * 100 : 0.0)
                        .build())
                .collect(Collectors.toList());

        // 按错误阶段分组
        Map<String, Integer> stageMap = new HashMap<>();
        for (FailureStatistics s : stats) {
            stageMap.merge(s.getErrorStage(), s.getCount(), Integer::sum);
        }
        List<FailureOverviewVO.ErrorStageStatistics> errorStageStats = stageMap.entrySet().stream()
                .map(e -> FailureOverviewVO.ErrorStageStatistics.builder()
                        .errorStage(e.getKey())
                        .count(e.getValue())
                        .percentage(failedTurns > 0 ? (double) e.getValue() / failedTurns * 100 : 0.0)
                        .build())
                .collect(Collectors.toList());

        return FailureOverviewVO.builder()
                .totalTurns(totalTurns)
                .failedTurns(failedTurns)
                .failureRate(failureRate)
                .errorCodeStats(errorCodeStats)
                .errorStageStats(errorStageStats)
                .build();
    }

    /**
     * 查询 Turn 列表
     */
    public List<AdminConversationTurn> listTurns(String sessionId, String status, String errorCode, int page, int size) {
        if (sessionId != null && !sessionId.isBlank()) {
            UUID conversationId = parseUuid(sessionId);
            if (conversationId != null) {
                return turnMapper.selectTurnsBySessionId(conversationId, size);
            }
        }
        // TODO(#ADMIN-101): 实现通用查询 - 支持按 sessionId、status、errorCode 组合条件查询
        return Collections.emptyList();
    }

    /**
     * 统计 Turn 总数
     */
    public int countTurns(String sessionId, String status, String errorCode) {
        // TODO(#ADMIN-102): 实现计数 - 支持按 sessionId、status、errorCode 组合条件统计总数
        return 0;
    }

    /**
     * 获取 Turn 详情
     */
    public Map<String, Object> getTurnDetail(String turnId) {
        AdminConversationTurn turn = turnMapper.selectByTurnId(turnId);
        if (turn == null) {
            return Collections.emptyMap();
        }

        Map<String, Object> result = new HashMap<>();
        result.put("turn", turn);
        result.put("sessionId", turn.getConversationId() != null ? turn.getConversationId().toString() : null);
        result.put("userId", turn.getUserId() != null ? turn.getUserId().toString() : null);
        return result;
    }

    /**
     * 获取幂等冲突统计
     */
    public Map<String, Object> getIdempotencyConflicts(String dateFrom, String dateTo) {
        LocalDate from = dateFrom != null ? LocalDate.parse(dateFrom) : LocalDate.now().minusDays(7);
        LocalDate to = dateTo != null ? LocalDate.parse(dateTo) : LocalDate.now();

        List<Map<String, Object>> dailyStats = new ArrayList<>();
        LocalDate current = from;
        DateTimeFormatter formatter = DateTimeFormatter.BASIC_ISO_DATE;

        while (!current.isAfter(to)) {
            String key = IDEMPOTENCY_CONFLICT_METRIC_KEY_PREFIX + current.format(formatter);
            Long count = (Long) redisTemplate.opsForValue().get(key);

            Map<String, Object> stat = new HashMap<>();
            stat.put("date", current.toString());
            stat.put("count", count != null ? count : 0);
            dailyStats.add(stat);

            current = current.plusDays(1);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("daily", dailyStats);
        result.put("total", dailyStats.stream().mapToInt(s -> ((Number) s.get("count")).intValue()).sum());
        return result;
    }

    private LocalDateTime parseDate(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) {
            return LocalDate.now().minusDays(7).atStartOfDay();
        }
        try {
            return LocalDateTime.parse(dateStr);
        } catch (Exception e) {
            return LocalDate.parse(dateStr).atStartOfDay();
        }
    }

    private UUID parseUuid(String uuidStr) {
        if (uuidStr == null || uuidStr.isBlank()) {
            return null;
        }
        try {
            return UUID.fromString(uuidStr);
        } catch (Exception e) {
            return null;
        }
    }
}
