package com.echoes.conversation.domain.chat.application;

import com.echoes.conversation.domain.chat.entity.vo.ChatResponseVO;
import com.echoes.conversation.domain.chat.service.ITurnEventService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * 流式聊天 SSE 格式化器
 * 负责将响应数据格式化为 SSE 格式并持久化
 */
@Slf4j
@Component
public class ChatStreamSSEFormatter {

    private final ITurnEventService turnEventService;
    private final ObjectMapper objectMapper;

    public ChatStreamSSEFormatter(ITurnEventService turnEventService, ObjectMapper objectMapper) {
        this.turnEventService = turnEventService;
        this.objectMapper = objectMapper;
    }

    /**
     * 格式化 SSE 并持久化
     */
    public String formatSSEAndPersist(String type, Object data, String traceId, String sessionId, String turnId, String protocolVersion) {
        try {
            String eventJson = turnEventService.appendEvent(sessionId, turnId, type, data, traceId, protocolVersion);
            return "data: " + eventJson + "\n\n";
        } catch (Exception e) {
            log.error("格式化并持久化 SSE 数据失败", e);
            return "data: {\"type\":\"error\",\"data\":\"格式化失败\"}\n\n";
        }
    }

    /**
     * 解析音频块数据
     */
    public Object parseAudioChunkData(String audioChunk) {
        if (audioChunk == null || audioChunk.isBlank()) {
            return null;
        }
        try {
            String payload = audioChunk.trim();
            // Be tolerant to SSE-wrapped payloads: "data: {...}"
            if (payload.startsWith("data:")) {
                payload = payload.substring(5).trim();
            }
            JsonNode node = objectMapper.readTree(payload);
            JsonNode audioData = node.get("audioData");
            if (audioData != null && !audioData.isNull()) {
                Map<String, Object> audioMap = new HashMap<>();
                audioMap.put("audio", audioData.asText());
                audioMap.put("mime", "audio/wav");
                audioMap.put("format", "wav");
                audioMap.put("sample_rate", 24000);
                return audioMap;
            }
        } catch (Exception e) {
            log.debug("Failed to parse audio chunk JSON, fallback to raw string: {}", e.getMessage());
        }
        return audioChunk;
    }

    /**
     * 映射聊天响应到 SSE
     */
    public String mapChatResponseToSse(ChatResponseVO response, String traceId, String sessionId, String turnId, String protocolVersion) {
        if (response == null) {
            return formatSSEAndPersist(
                    "error",
                    buildErrorData("EMPTY_RESPONSE", "empty response", "voice_response_parse", true, 502, null, "Retry later."),
                    traceId,
                    sessionId,
                    turnId,
                    protocolVersion);
        }

        String type = response.getType();
        if (type == null || type.isBlank()) {
            type = response.getAudioData() != null ? "audio_chunk" : "text";
        }

        Object data = null;
        if ("text".equals(type)) {
            data = response.getContent() != null ? response.getContent() : response.getDelta();
        } else if ("audio_chunk".equals(type) || "audio".equals(type)) {
            if (response.getAudioData() != null && response.getAudioData().length > 0) {
                Map<String, Object> audioData = new HashMap<>();
                audioData.put("audio", java.util.Base64.getEncoder().encodeToString(response.getAudioData()));
                audioData.put("mime", "audio/wav");
                audioData.put("format", "wav");
                audioData.put("sample_rate", 24000);
                data = audioData;
                type = "audio_chunk";
            }
        } else if ("error".equals(type)) {
            String message = response.getContent() != null ? response.getContent() : "voice stream error";
            data = buildErrorData("VOICE_STREAM_ERROR", message, "voice_response_parse", true, 502, null, "Retry later or switch to default voice.");
        }

        return formatSSEAndPersist(type, data, traceId, sessionId, turnId, protocolVersion);
    }

    /**
     * 构建错误数据
     */
    public Map<String, Object> buildErrorData(
            String code,
            String message,
            String stage,
            boolean retryable,
            int httpStatus,
            Map<String, Object> details,
            String suggestedAction) {
        Map<String, Object> error = new HashMap<>();
        error.put("code", code);
        error.put("message", message == null ? "unknown error" : message);
        error.put("stage", stage);
        error.put("retryable", retryable);
        error.put("http_status", httpStatus);
        error.put("details", details == null ? Map.of() : details);
        error.put("suggested_action", suggestedAction);
        return error;
    }
}
