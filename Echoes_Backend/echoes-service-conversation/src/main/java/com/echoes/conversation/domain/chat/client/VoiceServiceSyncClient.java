package com.echoes.conversation.domain.chat.client;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import java.net.URI;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
public class VoiceServiceSyncClient {

    private final VoiceServiceErrorHandler errorHandler;
    private final WebClient webClient;
    private final WebClient directClient;
    private final String echoesAiDirectUrl;
    private final String nacosServerAddr;
    private final String nacosNamespace;
    private final String nacosGroup;

    private static final String VOICE_SERVICE_NAME = "echoes-service-voice";
    private static final String SYNTHESIZE_TEXT_PATH = "/internal/voice/inference/synthesize-text";
    private static final String SYNTHESIZE_TEXT_REF_PATH = "/internal/voice/inference/synthesize-text-ref";
    private static final String VOICE_REF_GET_PATH = "/internal/voice/assets/ref/{refId}";

    public VoiceServiceSyncClient(
            VoiceServiceErrorHandler errorHandler,
            WebClient webClient,
            WebClient directClient,
            String echoesAiDirectUrl,
            String nacosServerAddr,
            String nacosNamespace,
            String nacosGroup) {
        this.errorHandler = errorHandler;
        this.webClient = webClient;
        this.directClient = directClient;
        this.echoesAiDirectUrl = echoesAiDirectUrl;
        this.nacosServerAddr = nacosServerAddr;
        this.nacosNamespace = nacosNamespace;
        this.nacosGroup = nacosGroup;
    }

    public Mono<String> synthesizeText(String text, String voiceName, String traceId, String sessionId, String turnId) {
        Map<String, String> requestBody = new HashMap<>();
        requestBody.put("text", text);
        requestBody.put("voiceName", voiceName);

        URI requestUri = buildLoadBalancerUri(SYNTHESIZE_TEXT_PATH);
        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        String errorMsg = String.format("Service %s has no available instances", VOICE_SERVICE_NAME);
                        log.warn("{}; nacos server={}, namespace={}, group={}",
                                errorMsg,
                                nacosServerAddr,
                                (nacosNamespace == null || nacosNamespace.isBlank()) ? "(empty)" : nacosNamespace,
                                nacosGroup);
                        if (echoesAiDirectUrl != null && !echoesAiDirectUrl.isBlank()) {
                            String directUrl = echoesAiDirectUrl + SYNTHESIZE_TEXT_PATH;
                            return directClient.post()
                                    .uri(directUrl)
                                    .contentType(MediaType.APPLICATION_JSON)
                                    .bodyValue(requestBody)
                                    .header("X-INTERNAL", "1")
                                    .header("X-TRACE-ID", safeHeaderValue(traceId))
                                    .header("X-SESSION-ID", safeHeaderValue(sessionId))
                                    .header("X-TURN-ID", safeHeaderValue(turnId))
                                    .retrieve()
                                    .bodyToMono(byte[].class)
                                    .map(bytes -> Base64.getEncoder().encodeToString(bytes));
                        }
                        return Mono.error(new IllegalStateException(errorMsg));
                    }

                    Mono<String> loadBalancedRequest = webClient.post()
                            .uri(requestUri)
                            .contentType(MediaType.APPLICATION_JSON)
                            .bodyValue(requestBody)
                            .header("X-INTERNAL", "1")
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .retrieve()
                            .onStatus(HttpStatusCode::isError, response -> response.bodyToMono(String.class)
                                    .defaultIfEmpty("empty body")
                                    .flatMap(errorBody -> {
                                        HttpStatusCode status = response.statusCode();
                                        return Mono.error(new WebClientResponseException(
                                                status.value(),
                                                status.toString(),
                                                response.headers().asHttpHeaders(),
                                                errorBody.getBytes(),
                                                null
                                        ));
                                    }))
                            .bodyToMono(byte[].class)
                            .map(bytes -> Base64.getEncoder().encodeToString(bytes));

                    return loadBalancedRequest.onErrorResume(error -> errorHandler.handleSyncError(
                            error,
                            instances,
                            requestUri,
                            text,
                            voiceName,
                            traceId,
                            sessionId,
                            turnId,
                            directClient,
                            requestBody));
                });
    }

    public Mono<JsonNode> getVoiceReference(String refId, String traceId, String sessionId, String turnId) {
        URI requestUri = buildLoadBalancerUri(VOICE_REF_GET_PATH.replace("{refId}", refId));
        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        return Mono.error(new IllegalStateException("voice service not available"));
                    }
                    return webClient.get()
                            .uri(requestUri)
                            .header("X-INTERNAL", "1")
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .retrieve()
                            .bodyToMono(JsonNode.class);
                });
    }

    public Mono<String> synthesizeTextWithRefId(String text, String refId, String traceId, String sessionId, String turnId) {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("text", text);
        requestBody.put("refId", refId);

        URI requestUri = buildLoadBalancerUri(SYNTHESIZE_TEXT_REF_PATH);
        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        String errorMsg = String.format("Service %s has no available instances", VOICE_SERVICE_NAME);
                        return Mono.error(new IllegalStateException(errorMsg));
                    }

                    return webClient.post()
                            .uri(requestUri)
                            .contentType(MediaType.APPLICATION_JSON)
                            .bodyValue(requestBody)
                            .header("X-INTERNAL", "1")
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .retrieve()
                            .onStatus(HttpStatusCode::isError, response -> response.bodyToMono(String.class)
                                    .defaultIfEmpty("empty body")
                                    .flatMap(errorBody -> {
                                        HttpStatusCode status = response.statusCode();
                                        return Mono.error(new WebClientResponseException(
                                                status.value(),
                                                status.toString(),
                                                response.headers().asHttpHeaders(),
                                                errorBody.getBytes(),
                                                null
                                        ));
                                    }))
                            .bodyToMono(byte[].class)
                            .map(bytes -> Base64.getEncoder().encodeToString(bytes));
                });
    }

    private Mono<String> fallbackToDirectInstance(
            List<org.springframework.cloud.client.ServiceInstance> instances,
            Map<String, String> requestBody,
            String text,
            String voiceName,
            String traceId,
            String sessionId,
            String turnId) {
        if (instances == null || instances.isEmpty()) {
            return Mono.error(new IllegalStateException("No available service instances"));
        }

        org.springframework.cloud.client.ServiceInstance instance = instances.get(0);
        String directUrl = instance.getUri() + SYNTHESIZE_TEXT_PATH;

        return directClient.post()
                .uri(directUrl)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(requestBody)
                .header("X-INTERNAL", "1")
                .header("X-TRACE-ID", safeHeaderValue(traceId))
                .header("X-SESSION-ID", safeHeaderValue(sessionId))
                .header("X-TURN-ID", safeHeaderValue(turnId))
                .retrieve()
                .bodyToMono(byte[].class)
                .map(bytes -> Base64.getEncoder().encodeToString(bytes));
    }

    private URI buildLoadBalancerUri(String path) {
        String normalizedPath = path.startsWith("/") ? path : "/" + path;
        return URI.create("lb://" + VOICE_SERVICE_NAME + normalizedPath);
    }

    private static String safeHeaderValue(String value) {
        return value == null ? "" : value;
    }
}
