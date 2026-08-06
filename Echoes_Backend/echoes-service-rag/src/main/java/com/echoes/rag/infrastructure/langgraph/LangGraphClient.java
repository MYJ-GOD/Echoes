package com.echoes.rag.infrastructure.langgraph;

import com.echoes.rag.config.RagProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

/**
 * LangGraph 服务 HTTP 客户端
 *
 * 支持：
 * - 流式/非流式 RAG 工作流调用
 * - 向量检索
 * - 混合检索（向量 + BM25）
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class LangGraphClient {

    private final WebClient.Builder webClientBuilder;
    private final RagProperties ragProperties;
    private final ObjectMapper objectMapper;

    /**
     * 流式调用 LangGraph 工作流
     * 返回 NDJSON 格式的 Flux
     */
    public Flux<JsonNode> streamWorkflow(RagWorkflowRequest request) {
        return webClientBuilder.build()
            .post()
            .uri(ragProperties.getLanggraphUrl() + "/rag/chat/stream")
            .bodyValue(request)
            .retrieve()
            .bodyToFlux(String.class)
            .map(this::parseNdjsonLine)
            .doOnError(error -> log.error("LangGraph stream error", error));
    }

    /**
     * 非流式调用
     */
    public Mono<RagWorkflowResponse> executeWorkflow(RagWorkflowRequest request) {
        return webClientBuilder.build()
            .post()
            .uri(ragProperties.getLanggraphUrl() + "/rag/chat")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(RagWorkflowResponse.class);
    }

    /**
     * 向量检索
     */
    public Mono<SearchResponse> search(SearchRequest request) {
        return webClientBuilder.build()
            .post()
            .uri(ragProperties.getLanggraphUrl() + "/search")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(SearchResponse.class);
    }

    /**
     * 混合检索（向量 + BM25）
     */
    public Mono<HybridSearchResponse> hybridSearch(HybridSearchRequest request) {
        return webClientBuilder.build()
            .post()
            .uri(ragProperties.getLanggraphUrl() + "/search/hybrid")
            .bodyValue(request)
            .retrieve()
            .bodyToMono(HybridSearchResponse.class);
    }

    /**
     * 获取检索指标
     */
    public Mono<JsonNode> getMetrics(int days) {
        return webClientBuilder.build()
            .get()
            .uri(ragProperties.getLanggraphUrl() + "/metrics?days=" + days)
            .retrieve()
            .bodyToMono(JsonNode.class);
    }

    /**
     * 详细健康检查
     */
    public Mono<JsonNode> detailedHealthCheck() {
        return webClientBuilder.build()
            .get()
            .uri(ragProperties.getLanggraphUrl() + "/health/detailed")
            .retrieve()
            .bodyToMono(JsonNode.class);
    }

    private JsonNode parseNdjsonLine(String line) {
        try {
            return objectMapper.readTree(line);
        } catch (Exception e) {
            log.warn("Failed to parse NDJSON line: {}", line, e);
            return null;
        }
    }
}
