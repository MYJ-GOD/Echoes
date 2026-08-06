package com.echoes.rag.infrastructure.langgraph;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 混合检索请求（向量 + BM25）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HybridSearchRequest {

    /**
     * 查询文本
     */
    private String query;

    /**
     * 知识库 ID 列表
     */
    private List<String> kbIds;

    /**
     * 返回数量
     */
    private Integer topK;

    /**
     * 最低相似度阈值
     */
    private Double threshold;

    /**
     * 向量检索权重 (0-1)
     * 默认 0.7，表示向量占 70%，BM25 占 30%
     */
    private Double alpha;

    /**
     * 是否使用 Rerank
     */
    @JsonProperty("use_rerank")
    private Boolean useRerank;
}
