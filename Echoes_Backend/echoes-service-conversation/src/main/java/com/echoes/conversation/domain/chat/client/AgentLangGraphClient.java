package com.echoes.conversation.domain.chat.client;

import com.echoes.conversation.config.LanggraphProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.Map;

/**
 * echoes-langgraph Agent 编排服务客户端（Week3）
 * <p>
 * 调 {@code /agent/chat/stream}（NDJSON），解析 message.delta 事件文本，
 * 输出与 Spring AI 直连一致的 {@code Flux<String>}，上层 SSE 流程无需改动。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AgentLangGraphClient {

    private final WebClient.Builder webClientBuilder;
    private final LanggraphProperties langgraphProperties;
    private final ObjectMapper objectMapper;

    /**
     * 流式调用 Agent 编排
     *
     * @param message   用户输入
     * @param sessionId 会话 ID（作为 checkpointer thread_id）
     * @param turnId    Turn ID
     * @param userId    用户 ID
     * @return 文本流（message.delta 内容）
     */
    public Flux<String> streamChat(String message, String sessionId, String turnId, String userId) {
        Map<String, Object> body = Map.of(
                "query", message,
                "user_id", userId == null ? "" : userId,
                "session_id", sessionId == null ? "" : sessionId,
                "turn_id", turnId == null ? "" : turnId,
                "conversation_history", List.of()
        );
        return webClientBuilder.build()
                .post()
                .uri(langgraphProperties.getUrl() + "/agent/chat/stream")
                .header("X-INTERNAL", "1")
                .bodyValue(body)
                .retrieve()
                .bodyToFlux(String.class)
                .map(this::parseNdjsonText)
                .filter(text -> text != null && !text.isEmpty())
                .doOnError(e -> log.error("AgentLangGraph stream error", e));
    }

    private String parseNdjsonText(String line) {
        try {
            JsonNode node = objectMapper.readTree(line);
            if ("message.delta".equals(node.path("type").asText())) {
                return node.path("content").asText();
            }
            return null;
        } catch (Exception e) {
            log.warn("Agent NDJSON 解析失败: {}", line, e);
            return null;
        }
    }
}
