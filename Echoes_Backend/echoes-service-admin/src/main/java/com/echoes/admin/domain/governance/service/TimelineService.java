package com.echoes.admin.domain.governance.service;

import com.echoes.admin.domain.governance.entity.vo.TimelineEventVO;
import com.echoes.admin.domain.governance.entity.vo.TimelineResponseVO;
import com.echoes.admin.domain.governance.entity.po.AdminConversationTurn;
import com.echoes.admin.domain.governance.repository.AdminConversationTurnMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/**
 * 时间线聚合服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TimelineService {

    private final AdminConversationTurnMapper turnMapper;

    /**
     * 根据 turnId 获取完整时间线
     */
    public TimelineResponseVO getTimelineByTurnId(String turnId) {
        AdminConversationTurn turn = turnMapper.selectByTurnId(turnId);
        if (turn == null) {
            return null;
        }

        List<TimelineEventVO> events = new ArrayList<>();

        // 1. Session 创建事件（如果有）
        if (turn.getStartTime() != null) {
            events.add(TimelineEventVO.builder()
                    .eventType("SESSION_START")
                    .eventTime(turn.getStartTime().minusSeconds(1))
                    .description("会话开始")
                    .referenceId(turn.getConversationId() != null ? turn.getConversationId().toString() : null)
                    .status("RUNNING")
                    .build());
        }

        // 2. Turn 开始事件
        events.add(TimelineEventVO.builder()
                .eventType("TURN_START")
                .eventTime(turn.getStartTime())
                .description("Turn 开始：" + turnId)
                .referenceId(turnId)
                .status(turn.getStatus())
                .build());

        // 3. 如果有 idempotency_key，记录
        if (turn.getIdempotencyKey() != null) {
            events.add(TimelineEventVO.builder()
                    .eventType("IDEMPOTENCY_CHECK")
                    .eventTime(turn.getStartTime())
                    .description("幂等性检查：" + turn.getIdempotencyKey())
                    .referenceId(turnId)
                    .status("SUCCESS")
                    .build());
        }

        // 4. 推理事件（如果有 voice_model_id）
        if (turn.getStatus() != null) {
            String description = turn.getStatus().equals("SUCCESS") ?
                    "推理成功" : ("推理失败：" + turn.getErrorCode());
            events.add(TimelineEventVO.builder()
                    .eventType("INFERENCE")
                    .eventTime(turn.getEndTime() != null ? turn.getEndTime() : turn.getStartTime())
                    .description(description)
                    .referenceId(turnId)
                    .status(turn.getStatus())
                    .errorCode(turn.getErrorCode())
                    .errorStage(turn.getErrorStage())
                    .build());
        }

        // 5. 审计事件（如果有）
        // 注：这里可以关联 voice_audit_log，但需要 voiceAssetId
        // 暂时跳过，等待后续扩展

        // 6. Turn 结束事件
        if (turn.getEndTime() != null) {
            events.add(TimelineEventVO.builder()
                    .eventType("TURN_END")
                    .eventTime(turn.getEndTime())
                    .description("Turn 结束")
                    .referenceId(turnId)
                    .status(turn.getStatus())
                    .build());
        }

        return TimelineResponseVO.builder()
                .sessionId(turn.getConversationId() != null ? turn.getConversationId().toString() : null)
                .turnId(turnId)
                .events(events)
                .build();
    }
}
