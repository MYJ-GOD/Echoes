package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.domain.chat.entity.po.ConversationSession;
import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;
import com.echoes.conversation.domain.chat.repository.ConversationSessionRepository;
import com.echoes.conversation.domain.chat.repository.ConversationTurnRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * Conversation Internal API（内部服务调用）
 * 供 admin 等内部服务只读访问 conversation 数据，不对外暴露
 *
 * @author echoes
 */
@Slf4j
@RestController
@RequestMapping("/internal/conversation")
@RequiredArgsConstructor
@Tag(name = "Conversation Internal API", description = "内部服务调用接口（admin 等）")
public class ConversationInternalController {

    private final ConversationSessionRepository sessionRepository;
    private final ConversationTurnRepository turnRepository;

    /**
     * 获取会话详情
     */
    @Operation(summary = "获取会话详情", description = "根据 conversationId 获取会话详情（内部调用）")
    @GetMapping("/sessions/{conversationId}")
    public ConversationSession getSession(
            @PathVariable("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: getSession conversationId={}, X-INTERNAL={}", conversationId, internal);
        return sessionRepository.findById(conversationId).orElse(null);
    }

    /**
     * 获取会话列表
     */
    @Operation(summary = "获取会话列表", description = "根据 userId 获取会话列表（内部调用）")
    @GetMapping("/sessions")
    public List<ConversationSession> listSessions(
            @RequestParam(value = "userId", required = false) UUID userId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: listSessions userId={}, X-INTERNAL={}", userId, internal);
        if (userId != null) {
            // 使用现有方法：findByUserIdAndIsDeletedOrderByLastMessageTimeDesc，仅返回未删除的会话
            return sessionRepository.findByUserIdAndIsDeletedOrderByLastMessageTimeDesc(userId, 0);
        }
        return List.of();
    }

    /**
     * 获取 Turn 详情
     */
    @Operation(summary = "获取 Turn 详情", description = "根据 turnId 获取对话轮次详情（内部调用）")
    @GetMapping("/turns/{turnId}")
    public ConversationTurn getTurn(
            @PathVariable("turnId") String turnId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: getTurn turnId={}, X-INTERNAL={}", turnId, internal);
        return turnRepository.findByTurnId(turnId);
    }

    /**
     * 按会话 ID 获取 Turn 列表
     * 注：TurnRepository 无 findByConversationId 方法，需要 admin 改用 getTurn 单查或扩展 repository
     */
    @Operation(summary = "按会话 ID 获取 Turn 列表", description = "根据 conversationId 获取对话轮次列表（内部调用）")
    @GetMapping("/turns")
    public List<ConversationTurn> listTurnsBySessionId(
            @RequestParam("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: listTurnsBySessionId conversationId={}, X-INTERNAL={}", conversationId, internal);
        // TODO: TurnRepository 需增加 List<ConversationTurn> findByConversationId(UUID) 方法
        // 暂返回空列表，待扩展 repository
        log.warn("InternalAPI: listTurnsBySessionId not implemented, returning empty list");
        return List.of();
    }
}
