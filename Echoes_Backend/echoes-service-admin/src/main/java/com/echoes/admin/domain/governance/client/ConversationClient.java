package com.echoes.admin.domain.governance.client;

import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;
import com.echoes.conversation.domain.chat.entity.po.ConversationSession;
import com.echoes.conversation.domain.chat.entity.po.ConversationSummary;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.UUID;

/**
 * Conversation Service Feign 客户端
 * 用于 admin 模块只读访问 conversation 服务数据
 */
@FeignClient(
        name = "echoes-service-conversation",
        path = "/internal/conversation",
        contextId = "conversationClient",
        configuration = com.echoes.admin.config.FeignConfig.class
)
public interface ConversationClient {

    /**
     * 获取会话详情
     */
    @GetMapping("/internal/conversation/sessions/{conversationId}")
    ConversationSession getSession(
            @PathVariable("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 获取会话列表
     */
    @GetMapping("/internal/conversation/sessions")
    List<ConversationSession> listSessions(
            @RequestParam(value = "userId", required = false) UUID userId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 获取 Turn 详情
     */
    @GetMapping("/internal/conversation/turns/{turnId}")
    ConversationTurn getTurn(
            @PathVariable("turnId") String turnId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 按会话 ID 获取 Turn 列表
     */
    @GetMapping("/internal/conversation/turns")
    List<ConversationTurn> listTurnsBySessionId(
            @RequestParam("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 获取会话摘要
     */
    @GetMapping("/internal/conversation/summary/{conversationId}")
    ConversationSummary getSummary(
            @PathVariable("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );
}
