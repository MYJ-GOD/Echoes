package com.echoes.rag.infrastructure.langgraph;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * RAG 工作流响应
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RagWorkflowResponse {

    /**
     * 生成的回答
     */
    private String response;

    /**
     * 检索到的上下文
     */
    private List<ContextChunk> context;

    /**
     * 引用来源
     */
    private List<Citation> citations;

    /**
     * 延迟（毫秒）
     */
    private Integer latencyMs;

    /**
     * 降级原因
     */
    private String fallbackReason;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ContextChunk {
        private String chunkId;
        private String content;
        private Double score;
        private DocumentInfo document;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Citation {
        private Integer index;
        private DocumentInfo document;
        private String chunkId;
        private Double score;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DocumentInfo {
        private String title;
        private String sourceUrl;
    }
}
