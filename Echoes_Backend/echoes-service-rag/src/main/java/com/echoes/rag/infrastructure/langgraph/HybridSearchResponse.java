package com.echoes.rag.infrastructure.langgraph;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 混合检索响应
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HybridSearchResponse {

    /**
     * 检索结果列表
     */
    private List<SearchResponse.SearchResult> results;

    /**
     * 检索方法
     */
    @JsonProperty("retrieval_method")
    private String retrievalMethod;

    /**
     * 向量检索结果数量
     */
    @JsonProperty("vector_count")
    private Integer vectorCount;

    /**
     * BM25 检索结果数量
     */
    @JsonProperty("bm25_count")
    private Integer bm25Count;

    /**
     * 最终结果数量
     */
    @JsonProperty("final_count")
    private Integer finalCount;

    /**
     * 延迟（毫秒）
     */
    @JsonProperty("latency_ms")
    private Integer latencyMs;
}
