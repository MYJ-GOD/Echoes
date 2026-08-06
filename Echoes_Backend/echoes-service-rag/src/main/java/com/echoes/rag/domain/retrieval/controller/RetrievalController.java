package com.echoes.rag.domain.retrieval.controller;

import com.echoes.rag.infrastructure.langgraph.HybridSearchRequest;
import com.echoes.rag.infrastructure.langgraph.HybridSearchResponse;
import com.echoes.rag.infrastructure.langgraph.LangGraphClient;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

/**
 * 检索管理 API
 *
 * 提供向量检索、混合检索等功能
 */
@Slf4j
@RestController
@RequestMapping("/api/rag/retrieval")
@RequiredArgsConstructor
@Tag(name = "检索管理", description = "Retrieval Management API")
public class RetrievalController {

    private final LangGraphClient langGraphClient;

    /**
     * 混合检索（向量 + BM25）
     */
    @PostMapping("/hybrid")
    @Operation(summary = "混合检索")
    public Mono<ResponseEntity<HybridSearchResponse>> hybridSearch(
            @RequestBody HybridSearchRequest request
    ) {
        log.info("Hybrid search request: query={}, kbIds={}, topK={}",
                request.getQuery(), request.getKbIds(), request.getTopK());

        return langGraphClient.hybridSearch(request)
                .map(ResponseEntity::ok)
                .onErrorResume(error -> {
                    log.error("Hybrid search failed", error);
                    return Mono.just(ResponseEntity.internalServerError().build());
                });
    }

    /**
     * 获取检索指标
     */
    @GetMapping("/metrics")
    @Operation(summary = "获取检索指标")
    public Mono<ResponseEntity<com.fasterxml.jackson.databind.JsonNode>> getMetrics(
            @RequestParam(defaultValue = "7") int days
    ) {
        return langGraphClient.getMetrics(days)
                .map(ResponseEntity::ok)
                .onErrorResume(error -> {
                    log.error("Get metrics failed", error);
                    return Mono.just(ResponseEntity.internalServerError().build());
                });
    }

    /**
     * 详细健康检查
     */
    @GetMapping("/health")
    @Operation(summary = "详细健康检查")
    public Mono<ResponseEntity<com.fasterxml.jackson.databind.JsonNode>> detailedHealthCheck() {
        return langGraphClient.detailedHealthCheck()
                .map(ResponseEntity::ok)
                .onErrorResume(error -> {
                    log.error("Health check failed", error);
                    return Mono.just(ResponseEntity.internalServerError().build());
                });
    }
}
