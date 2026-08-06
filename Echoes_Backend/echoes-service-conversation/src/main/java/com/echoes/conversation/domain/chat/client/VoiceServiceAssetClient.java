package com.echoes.conversation.domain.chat.client;

import com.echoes.conversation.domain.chat.entity.dto.VoiceReferenceDTO;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

@Slf4j
public class VoiceServiceAssetClient {

    private final VoiceServiceErrorHandler errorHandler;
    private final WebClient webClient;

    private static final String VOICE_SERVICE_NAME = "echoes-service-voice";
    private static final String VOICE_REF_UPLOAD_PATH = "/internal/voice/assets/ref/upload";
    private static final String VOICE_REF_SIGNED_PATH = "/internal/voice/assets/ref/signed";
    private static final String VOICE_UPLOAD_OBJECT_PATH = "/internal/voice/assets/ref/upload-object";
    private static final String VOICE_ASSET_CREATE_PATH = "/internal/voice/assets";

    public VoiceServiceAssetClient(
            VoiceServiceErrorHandler errorHandler,
            WebClient webClient) {
        this.errorHandler = errorHandler;
        this.webClient = webClient;
    }

    public Mono<VoiceReferenceDTO> uploadVoiceReference(
            byte[] audioData, String filename, String refText, String userId,
            String traceId, String sessionId, String turnId) {

        org.springframework.http.client.MultipartBodyBuilder builder = new org.springframework.http.client.MultipartBodyBuilder();
        builder.part("audio_file", new org.springframework.core.io.ByteArrayResource(audioData))
                .filename(filename)
                .contentType(MediaType.APPLICATION_OCTET_STREAM);

        if (refText != null && !refText.trim().isEmpty()) {
            builder.part("ref_text", refText);
        }

        URI requestUri = buildLoadBalancerUri(VOICE_REF_UPLOAD_PATH);
        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        String errorMsg = String.format("Service %s has no available instances", VOICE_SERVICE_NAME);
                        return Mono.error(new IllegalStateException(errorMsg));
                    }

                    return webClient.post()
                            .uri(requestUri)
                            .body(BodyInserters.fromMultipartData(builder.build()))
                            .header("X-USER-ID", safeHeaderValue(userId))
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .retrieve()
                            .bodyToMono(JsonNode.class)
                            .map(jsonNode -> {
                                VoiceReferenceDTO dto = new VoiceReferenceDTO();
                                dto.setRefId(jsonNode.get("ref_id").asText());
                                dto.setRefText(jsonNode.has("ref_text") ? jsonNode.get("ref_text").asText() : "");
                                dto.setCreatedAt(System.currentTimeMillis());
                                return dto;
                            })
                            .onErrorResume(error -> Mono.error(new RuntimeException("voice ref upload failed: " + error.getMessage())));
                });
    }

    public Mono<JsonNode> createVoiceAsset(String requestBody, String userId) {
        URI requestUri = buildLoadBalancerUri(VOICE_ASSET_CREATE_PATH);
        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        String errorMsg = String.format("Service %s has no available instances", VOICE_SERVICE_NAME);
                        return Mono.error(new IllegalStateException(errorMsg));
                    }

                    return webClient.post()
                            .uri(requestUri)
                            .contentType(MediaType.APPLICATION_JSON)
                            .header("X-USER-ID", userId)
                            .body(BodyInserters.fromValue(requestBody))
                            .retrieve()
                            .bodyToMono(JsonNode.class)
                            .onErrorResume(error -> Mono.error(new RuntimeException("create voice asset failed: " + error.getMessage())));
                });
    }

    public Mono<JsonNode> uploadObject(
            byte[] audioData, String objectName,
            String traceId, String sessionId, String turnId) {

        org.springframework.http.client.MultipartBodyBuilder builder = new org.springframework.http.client.MultipartBodyBuilder();
        builder.part("audio_file", new org.springframework.core.io.ByteArrayResource(audioData))
                .filename(objectName)
                .contentType(MediaType.APPLICATION_OCTET_STREAM);
        builder.part("object_name", objectName);

        URI requestUri = buildLoadBalancerUri(VOICE_UPLOAD_OBJECT_PATH);

        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        return Mono.error(new IllegalStateException("voice service not available"));
                    }
                    return webClient.post()
                            .uri(requestUri)
                            .contentType(MediaType.MULTIPART_FORM_DATA)
                            .body(BodyInserters.fromMultipartData(builder.build()))
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .retrieve()
                            .bodyToMono(JsonNode.class);
                });
    }

    public Mono<JsonNode> getSignedUrl(String storageKey, String traceId, String sessionId, String turnId) {
        URI requestUri = buildLoadBalancerUri(
                VOICE_REF_SIGNED_PATH + "?storage_key=" + URLEncoder.encode(storageKey, StandardCharsets.UTF_8));

        return errorHandler.fetchInstances()
                .flatMap(instances -> {
                    if (instances == null || instances.isEmpty()) {
                        return Mono.error(new IllegalStateException("voice service not available"));
                    }
                    return webClient.get()
                            .uri(requestUri)
                            .header("X-TRACE-ID", safeHeaderValue(traceId))
                            .header("X-SESSION-ID", safeHeaderValue(sessionId))
                            .header("X-TURN-ID", safeHeaderValue(turnId))
                            .retrieve()
                            .bodyToMono(JsonNode.class);
                });
    }

    private URI buildLoadBalancerUri(String path) {
        String normalizedPath = path.startsWith("/") ? path : "/" + path;
        return URI.create("lb://" + VOICE_SERVICE_NAME + normalizedPath);
    }

    private static String safeHeaderValue(String value) {
        return value == null ? "" : value;
    }
}
