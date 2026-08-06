package com.echoes.conversation.domain.chat.client;

import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.vo.ChatResponseVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import java.net.URI;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
public class VoiceServiceStreamClient {

    private final VoiceServiceErrorHandler errorHandler;
    private final WebClient webClient;
    private final WebClient directStreamClient;

    private static final String VOICE_SERVICE_NAME = "echoes-service-voice";
    private static final String TTS_STREAM_PATH = "/internal/voice/inference/synthesize-stream";
    private static final String CHAT_STREAM_PATH = "/internal/voice/inference/synthesize-stream";

    public VoiceServiceStreamClient(
            VoiceServiceErrorHandler errorHandler,
            WebClient webClient,
            WebClient directStreamClient) {
        this.errorHandler = errorHandler;
        this.webClient = webClient;
        this.directStreamClient = directStreamClient;
    }

    public Flux<String> synthesizeStream(
            String voiceName,
            Flux<String> textStream,
            String traceId,
            String sessionId,
            String turnId,
            String userId) {

        if (voiceName == null || voiceName.trim().isEmpty()) {
            return Flux.error(new IllegalStateException("voiceName cannot be empty"));
        }
        if (!hasText(userId)) {
            return Flux.error(new IllegalStateException("X-USER-ID is required for voice synthesize stream"));
        }

        URI requestUri = buildLoadBalancerUri(TTS_STREAM_PATH + "?voiceName=" + voiceName);
        Flux<String> sseTextFrames = textStream.map(this::toSseEventFrame).cache();

        return Flux.defer(() -> errorHandler.fetchInstances()
                .flatMapMany(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        return Flux.error(new IllegalStateException("voice service not available"));
                    }

                    if (instances.size() == 1) {
                        return fallbackToDirectInstanceStream(instances, voiceName, sseTextFrames, traceId, sessionId, turnId, userId);
                    }

                    Flux<String> loadBalancedRequest = webClient.post()
                            .uri(requestUri)
                            .contentType(MediaType.TEXT_EVENT_STREAM)
                            .body(sseTextFrames, String.class)
                            .header("X-INTERNAL", "1")
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .header("X-USER-ID", safeHeaderValue(userId))
                            .retrieve()
                            .bodyToFlux(String.class);

                    return loadBalancedRequest.onErrorResume(error -> fallbackToDirectInstanceStream(
                            instances, voiceName, sseTextFrames, traceId, sessionId, turnId, userId));
                }));
    }

    public Flux<ChatResponseVO> streamChat(ChatRequestDTO request, String traceId, String sessionId, String turnId) {
        URI requestUri = buildLoadBalancerUri(CHAT_STREAM_PATH);

        Map<String, String> synthRequest = new HashMap<>();
        synthRequest.put("voiceName", "default");
        synthRequest.put("text", request.getMessage() != null ? request.getMessage() : "");

        return webClient.post()
                .uri(requestUri)
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.TEXT_EVENT_STREAM)
                .header("X-INTERNAL", "1")
                .header("X-TRACE-ID", safeHeaderValue(traceId))
                .header("X-SESSION-ID", safeHeaderValue(sessionId))
                .header("X-TURN-ID", safeHeaderValue(turnId))
                .bodyValue(synthRequest)
                .retrieve()
                .bodyToFlux(ChatResponseVO.class);
    }

    private Flux<String> fallbackToDirectInstanceStream(
            List<org.springframework.cloud.client.ServiceInstance> instances,
            String voiceName,
            Flux<String> textStream,
            String traceId,
            String sessionId,
            String turnId,
            String userId) {

        if (instances == null || instances.isEmpty()) {
            return Flux.error(new IllegalStateException("No available service instances"));
        }

        org.springframework.cloud.client.ServiceInstance instance = instances.get(0);
        String directUrl = instance.getUri() + TTS_STREAM_PATH + "?voiceName=" + voiceName;

        return directStreamClient.post()
                .uri(directUrl)
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .body(textStream, String.class)
                .header("X-INTERNAL", "1")
                .header("X-TRACE-ID", safeHeaderValue(traceId))
                .header("X-SESSION-ID", safeHeaderValue(sessionId))
                .header("X-TURN-ID", safeHeaderValue(turnId))
                .header("X-USER-ID", safeHeaderValue(userId))
                .retrieve()
                .bodyToFlux(String.class);
    }

    private URI buildLoadBalancerUri(String path) {
        String normalizedPath = path.startsWith("/") ? path : "/" + path;
        return URI.create("lb://" + VOICE_SERVICE_NAME + normalizedPath);
    }

    private String toSseEventFrame(String chunk) {
        String safe = chunk == null ? "" : chunk;
        return "data: " + safe + "\n\n";
    }

    private static String safeHeaderValue(String value) {
        return value == null ? "" : value;
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
