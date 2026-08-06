package com.echoes.conversation.domain.chat.client;

import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.client.discovery.DiscoveryClient;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;
import reactor.core.scheduler.Schedulers;

import java.net.URI;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 语音服务错误处理和回退客户端
 * 提供公共的错误处理逻辑和回退方案
 *
 * 包含方法：
 * - fetchInstances: 获取服务实例
 * - handleSyncError: 处理同步请求错误
 * - checkServiceAvailability: 检查服务可用性
 */
@Slf4j
@Service
public class VoiceServiceErrorHandler {

    private final DiscoveryClient discoveryClient;

    private static final String VOICE_SERVICE_NAME = "echoes-service-voice";

    public VoiceServiceErrorHandler(DiscoveryClient discoveryClient) {
        this.discoveryClient = discoveryClient;
    }

    /**
     * 非阻塞获取服务实例
     */
    public Mono<List<org.springframework.cloud.client.ServiceInstance>> fetchInstances() {
        return Mono.fromCallable(() -> discoveryClient.getInstances(VOICE_SERVICE_NAME))
                .subscribeOn(Schedulers.boundedElastic());
    }

    /**
     * 检查语音服务是否在 Nacos 中注册
     */
    public void checkServiceAvailability(String nacosServerAddr, String nacosNamespace, String nacosGroup) {
        try {
            log.info("🔍 检查语音服务可用性...");
            log.info("   当前服务 Nacos 配置：server-addr={}, namespace={}, group={}",
                    nacosServerAddr, nacosNamespace.isEmpty() ? "(空)" : nacosNamespace, nacosGroup);

            List<String> services = discoveryClient.getServices();
            boolean serviceExists = services.contains(VOICE_SERVICE_NAME);

            log.info("   当前 Nacos 中已注册的所有服务：{}", services);

            if (serviceExists) {
                List<org.springframework.cloud.client.ServiceInstance> instances =
                    discoveryClient.getInstances(VOICE_SERVICE_NAME);
                if (instances != null && !instances.isEmpty()) {
                    log.info("✅ 语音服务 {} 已注册到 Nacos，共 {} 个实例",
                            VOICE_SERVICE_NAME, instances.size());
                    instances.forEach(instance -> {
                        log.info("  - 实例：{}:{} (URI: {}, 实例 ID: {})",
                                instance.getHost(), instance.getPort(),
                                instance.getUri(), instance.getInstanceId());
                        log.debug("    元数据：{}", instance.getMetadata());
                    });
                } else {
                    log.warn("⚠️  语音服务 {} 在 Nacos 中注册但无可用实例", VOICE_SERVICE_NAME);
                    log.warn("   这可能导致 LoadBalancer 无法找到服务实例");
                }
            } else {
                log.error("❌ 语音服务 {} 未在 Nacos 中注册！", VOICE_SERVICE_NAME);
                log.error("   可能的原因：");
                log.error("   1. echoes-service-voice 服务未启动");
                log.error("   2. echoes-service-voice 连接到不同的 Nacos 服务器（应连接到：{}）", nacosServerAddr);
                log.error("   3. 命名空间不一致（当前：{}）", nacosNamespace.isEmpty() ? "(空)" : nacosNamespace);
                log.error("   4. 分组不一致（当前：{}）", nacosGroup);
                log.error("   5. Nacos 服务发现配置错误");
                log.error("   当前已注册的服务列表：{}", services);
            }
        } catch (Exception e) {
            log.error("检查语音服务可用性时出错：{}", e.getMessage(), e);
        }
    }

    /**
     * 处理同步请求错误
     */
    public Mono<String> handleSyncError(
            Throwable error,
            List<org.springframework.cloud.client.ServiceInstance> instances,
            URI requestUri,
            String text,
            String voiceName,
            String traceId,
            String sessionId,
            String turnId,
            WebClient directClient,
            Map<String, String> requestBody) {

        log.error("🔍 LoadBalancer 请求失败，开始诊断:");
        log.error("   错误类型：{}", error.getClass().getSimpleName());
        log.error("   错误信息：{}", error.getMessage());
        log.error("   请求 URI: {}", requestUri);

        try {
            List<String> allServices = discoveryClient.getServices();
            log.error("   当前 Nacos 中所有已注册的服务：{}", allServices);
            log.error("   查找的目标服务名：{}", VOICE_SERVICE_NAME);
            log.error("   服务是否存在：{}", allServices.contains(VOICE_SERVICE_NAME));

            List<org.springframework.cloud.client.ServiceInstance> errorInstances =
                discoveryClient.getInstances(VOICE_SERVICE_NAME);
            if (errorInstances == null || errorInstances.isEmpty()) {
                log.error("   ❌ 诊断：语音服务 {} 当前在 Nacos 中无可用实例", VOICE_SERVICE_NAME);
            } else {
                log.error("   ✅ 发现 {} 个实例:", errorInstances.size());
                errorInstances.forEach(instance -> {
                    log.error("      - 实例 ID: {}, IP: {}, 端口：{}, URI: {}, 元数据：{}",
                        instance.getInstanceId(), instance.getHost(),
                        instance.getPort(), instance.getUri(), instance.getMetadata());
                });
            }
        } catch (Exception e) {
            log.error("   检查服务实例时出错：{}", e.getMessage(), e);
        }

        boolean shouldFallback = false;
        if (error instanceof WebClientResponseException) {
            WebClientResponseException ex = (WebClientResponseException) error;
            int statusCode = ex.getStatusCode().value();
            String errorMessage = ex.getResponseBodyAsString();

            log.error("   HTTP 状态码：{}", statusCode);
            log.error("   错误响应体：{}", errorMessage);

            if (statusCode == 503) {
                shouldFallback = true;
                log.warn("⚠️ LoadBalancer 返回 503，尝试直接使用服务实例作为 fallback");
            } else if (errorMessage != null && errorMessage.contains("LoadBalancer")) {
                shouldFallback = true;
                log.warn("⚠️ LoadBalancer 错误，尝试直接使用服务实例，状态码：{}", statusCode);
            } else {
                log.error("语音合成失败，HTTP 状态：{}, 响应体：{}, 请求 URI: {}, 文本：{}, 音色：{}",
                        statusCode, errorMessage, requestUri, text, voiceName);
            }
        } else if (error instanceof IllegalStateException ||
                  (error.getMessage() != null && error.getMessage().contains("LoadBalancer"))) {
            shouldFallback = true;
            log.warn("⚠️ LoadBalancer 相关错误，尝试直接使用服务实例");
        } else {
            String errorType = error.getClass().getSimpleName();
            String errorMsg = error.getMessage();
            log.error("语音合成失败，请求 URI: {}, 文本：{}, 音色：{}, 错误类型：{}, 错误信息：{}",
                    requestUri, text, voiceName, errorType, errorMsg);
        }

        if (shouldFallback) {
            return fallbackToDirectInstance(instances, requestBody, text, voiceName, traceId, sessionId, turnId, directClient);
        }
        log.error("❌ 非 LoadBalancer 错误，不进行 fallback，直接抛出异常");
        return Mono.error(error);
    }

    /**
     * 回退方案：直接使用服务实例 URI，绕过 LoadBalancer
     */
    private Mono<String> fallbackToDirectInstance(
            List<org.springframework.cloud.client.ServiceInstance> instances,
            Map<String, String> requestBody,
            String text,
            String voiceName,
            String traceId,
            String sessionId,
            String turnId,
            WebClient directClient) {

        if (instances == null || instances.isEmpty()) {
            return Mono.error(new IllegalStateException("无可用服务实例"));
        }

        org.springframework.cloud.client.ServiceInstance instance = instances.get(0);
        java.net.URI instanceUri = instance.getUri();
        String baseUrl = instanceUri.toString();

        String SYNTHESIZE_TEXT_PATH = "/internal/voice/inference/synthesize-text";
        String path = SYNTHESIZE_TEXT_PATH.startsWith("/")
                ? SYNTHESIZE_TEXT_PATH
                : "/" + SYNTHESIZE_TEXT_PATH;
        String directUrl = baseUrl + path;

        log.info("使用直接实例 URL: {} (绕过 LoadBalancer)", directUrl);

        return directClient.post()
                .uri(directUrl)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(requestBody)
                .header("X-INTERNAL", "1")
                .header("X-TRACE-ID", safeHeaderValue(traceId))
                .header("X-SESSION-ID", safeHeaderValue(sessionId))
                .header("X-TURN-ID", safeHeaderValue(turnId))
                .retrieve()
                .onStatus(HttpStatusCode::isError, response -> {
                    return response.bodyToMono(String.class)
                            .defaultIfEmpty("无响应体")
                            .flatMap(errorBody -> {
                                HttpStatusCode status = response.statusCode();
                                log.error("直接实例请求返回错误，状态码：{}, 响应体：{}, URL: {}, 文本：{}",
                                        status, errorBody, directUrl, text);
                                return Mono.error(new WebClientResponseException(
                                        status.value(),
                                        status.toString(),
                                        response.headers().asHttpHeaders(),
                                        errorBody.getBytes(),
                                        null
                                ));
                            });
                })
                .bodyToMono(byte[].class)
                .map(bytes -> Base64.getEncoder().encodeToString(bytes))
                .doOnSuccess(audioBase64 -> log.info("通过直接实例成功生成语音，文本：{}, 音色：{}", text, voiceName))
                .doOnError(error -> log.error("直接实例请求也失败，URL: {}, 错误：{}", directUrl, error.getMessage()));
    }

    private static String safeHeaderValue(String value) {
        return value == null ? "" : value;
    }
}
