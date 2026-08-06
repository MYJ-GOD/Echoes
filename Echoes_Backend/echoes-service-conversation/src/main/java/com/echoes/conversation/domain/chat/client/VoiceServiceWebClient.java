package com.echoes.conversation.domain.chat.client;

import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.dto.VoiceReferenceDTO;
import com.echoes.conversation.domain.chat.entity.vo.ChatResponseVO;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.time.Duration;

@Slf4j
@Service
public class VoiceServiceWebClient {

    private final WebClient.Builder webClientBuilder;
    private final DiscoveryClient discoveryClient;
    private final VoiceServiceErrorHandler voiceServiceErrorHandler;

    @Value("${spring.cloud.nacos.discovery.server-addr:localhost:8848}")
    private String nacosServerAddr;

    @Value("${spring.cloud.nacos.discovery.namespace:}")
    private String nacosNamespace;

    @Value("${spring.cloud.nacos.discovery.group:DEFAULT_GROUP}")
    private String nacosGroup;

    @Value("${echoes.ai.direct-url:}")
    private String echoesAiDirectUrl;

    private VoiceServiceSyncClient voiceServiceSyncClient;
    private VoiceServiceStreamClient voiceServiceStreamClient;
    private VoiceServiceAssetClient voiceServiceAssetClient;

    private WebClient webClient;
    private WebClient directClient;
    private WebClient directStreamClient;

    public VoiceServiceWebClient(
            WebClient.Builder webClientBuilder,
            DiscoveryClient discoveryClient,
            VoiceServiceErrorHandler voiceServiceErrorHandler) {
        this.webClientBuilder = webClientBuilder;
        this.discoveryClient = discoveryClient;
        this.voiceServiceErrorHandler = voiceServiceErrorHandler;
    }

    @PostConstruct
    public void init() {
        HttpClient httpClient = HttpClient.create(
                        ConnectionProvider.builder("voice-loadbalanced")
                                .maxConnections(50)
                                .pendingAcquireTimeout(Duration.ofSeconds(10))
                                .build())
                .responseTimeout(Duration.ofMinutes(5))
                .option(io.netty.channel.ChannelOption.CONNECT_TIMEOUT_MILLIS, 10000);

        this.webClient = webClientBuilder
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
                .build();

        voiceServiceErrorHandler.checkServiceAvailability(nacosServerAddr, nacosNamespace, nacosGroup);

        HttpClient directHttpClient = HttpClient.create(
                        ConnectionProvider.builder("voice-direct")
                                .maxConnections(50)
                                .pendingAcquireTimeout(Duration.ofSeconds(10))
                                .build())
                .responseTimeout(Duration.ofMinutes(5))
                .option(io.netty.channel.ChannelOption.CONNECT_TIMEOUT_MILLIS, 10000);

        this.directClient = WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(directHttpClient))
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
                .build();

        HttpClient directStreamHttpClient = HttpClient.create(
                        ConnectionProvider.builder("voice-direct-stream")
                                .maxConnections(50)
                                .pendingAcquireTimeout(Duration.ofSeconds(10))
                                .build())
                .responseTimeout(Duration.ofMinutes(10))
                .option(io.netty.channel.ChannelOption.CONNECT_TIMEOUT_MILLIS, 10000);

        this.directStreamClient = WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(directStreamHttpClient))
                .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(10 * 1024 * 1024))
                .build();

        this.voiceServiceSyncClient = new VoiceServiceSyncClient(
                voiceServiceErrorHandler, webClient, directClient,
                echoesAiDirectUrl, nacosServerAddr, nacosNamespace, nacosGroup);
        this.voiceServiceStreamClient = new VoiceServiceStreamClient(
                voiceServiceErrorHandler, webClient, directStreamClient);
        this.voiceServiceAssetClient = new VoiceServiceAssetClient(
                voiceServiceErrorHandler, webClient);

        log.info("VoiceServiceWebClient initialized");
    }

    public Mono<String> synthesizeText(String text, String voiceName, String traceId, String sessionId, String turnId) {
        return voiceServiceSyncClient.synthesizeText(text, voiceName, traceId, sessionId, turnId);
    }

    public Mono<JsonNode> getVoiceReference(String refId, String traceId, String sessionId, String turnId) {
        return voiceServiceSyncClient.getVoiceReference(refId, traceId, sessionId, turnId);
    }

    public Mono<String> synthesizeTextWithRefId(String text, String refId, String traceId, String sessionId, String turnId) {
        return voiceServiceSyncClient.synthesizeTextWithRefId(text, refId, traceId, sessionId, turnId);
    }

    public Flux<String> synthesizeStream(
            String voiceName,
            Flux<String> textStream,
            String traceId,
            String sessionId,
            String turnId,
            String userId) {
        return voiceServiceStreamClient.synthesizeStream(voiceName, textStream, traceId, sessionId, turnId, userId);
    }

    public Flux<ChatResponseVO> streamChat(ChatRequestDTO request, String traceId, String sessionId, String turnId) {
        return voiceServiceStreamClient.streamChat(request, traceId, sessionId, turnId);
    }

    public Mono<VoiceReferenceDTO> uploadVoiceReference(
            byte[] audioData, String filename, String refText, String userId,
            String traceId, String sessionId, String turnId) {
        return voiceServiceAssetClient.uploadVoiceReference(audioData, filename, refText, userId, traceId, sessionId, turnId);
    }

    public Mono<JsonNode> createVoiceAsset(String requestBody, String userId) {
        return voiceServiceAssetClient.createVoiceAsset(requestBody, userId);
    }

    public Mono<JsonNode> uploadObject(byte[] audioData, String objectName, String traceId, String sessionId, String turnId) {
        return voiceServiceAssetClient.uploadObject(audioData, objectName, traceId, sessionId, turnId);
    }

    public Mono<JsonNode> getSignedUrl(String storageKey, String traceId, String sessionId, String turnId) {
        return voiceServiceAssetClient.getSignedUrl(storageKey, traceId, sessionId, turnId);
    }
}
