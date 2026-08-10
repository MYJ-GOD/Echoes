package com.echoes.admin.domain.governance.client;

import com.echoes.admin.domain.governance.dto.ConversationSessionDTO;
import com.echoes.admin.domain.governance.dto.ConversationSummaryDTO;
import com.echoes.admin.domain.governance.dto.ConversationTurnDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.UUID;

/**
 * Conversation Service Feign 客户端（使用 admin 本地 DTO，解耦 conversation jar 依赖）
 * 注：path 已含 /internal/conversation，方法路径无需重复前缀
 */
@FeignClient(
        name = "echoes-service-conversation",
        path = "/internal/conversation",
        contextId = "conversationClient",
        configuration = com.echoes.admin.config.FeignConfig.class
)
public interface ConversationClient {

    @GetMapping("/sessions/{conversationId}")
    ConversationSessionDTO getSession(
            @PathVariable("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/sessions")
    List<ConversationSessionDTO> listSessions(
            @RequestParam(value = "userId", required = false) UUID userId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/turns/{turnId}")
    ConversationTurnDTO getTurn(
            @PathVariable("turnId") String turnId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/turns")
    List<ConversationTurnDTO> listTurnsBySessionId(
            @RequestParam("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/summary/{conversationId}")
    ConversationSummaryDTO getSummary(
            @PathVariable("conversationId") UUID conversationId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );
}
