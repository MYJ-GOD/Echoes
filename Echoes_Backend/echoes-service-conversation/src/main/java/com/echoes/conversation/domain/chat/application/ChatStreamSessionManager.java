package com.echoes.conversation.domain.chat.application;

import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;
import com.echoes.conversation.domain.chat.repository.ConversationSessionRepository;
import com.echoes.conversation.domain.chat.service.ITurnService;
import com.echoes.utils.UuidUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 流式聊天会话管理器
 * 负责会话解析、用户 ID 解析、回合管理
 */
@Slf4j
@Component
public class ChatStreamSessionManager {

    private final ConversationSessionRepository conversationSessionRepository;
    private final ITurnService turnService;

    public ChatStreamSessionManager(
            ConversationSessionRepository conversationSessionRepository,
            ITurnService turnService) {
        this.conversationSessionRepository = conversationSessionRepository;
        this.turnService = turnService;
    }

    /**
     * 解析会话 ID
     */
    public UUID parseSessionId(String sessionId) {
        return UuidUtils.parseLenient(sessionId);
    }

    /**
     * 解析用户 ID（从请求或会话）
     */
    public AtomicReference<UUID> resolveUserId(
            String sysUserId,
            UUID sessionId) {
        AtomicReference<UUID> userIdRef = new AtomicReference<>(null);

        if (sysUserId != null && !sysUserId.isBlank()) {
            try {
                userIdRef.set(UuidUtils.parseLenient(sysUserId));
            } catch (Exception e) {
                log.debug("Invalid sysUserId in request: {}", e.getMessage());
            }
        }

        if (userIdRef.get() == null && sessionId != null) {
            try {
                var conv = conversationSessionRepository.findById(sessionId).orElse(null);
                if (conv != null && (conv.getIsDeleted() == null || conv.getIsDeleted() == 0)) {
                    userIdRef.set(conv.getUserId());
                }
            } catch (Exception e) {
                log.debug("Failed to resolve userId from conversation_session: {}", e.getMessage());
            }
        }

        return userIdRef;
    }

    /**
     * 开始回合（带幂等性校验）
     */
    public ConversationTurn startTurn(
            UUID sessionId,
            String turnId,
            UUID userId,
            String idempotencyKey,
            byte[] payloadHash) {
        return turnService.startTurn(sessionId, turnId, userId, idempotencyKey, payloadHash);
    }

    /**
     * 完成回合
     */
    public void completeTurn(String turnId, UUID messageId) {
        turnService.completeTurn(turnId, messageId != null ? messageId.toString() : null);
    }

    /**
     * 失败回合
     */
    public void failTurn(String turnId, String reason, String stage, boolean retryable) {
        turnService.failTurn(turnId, reason, stage, retryable);
    }
}
