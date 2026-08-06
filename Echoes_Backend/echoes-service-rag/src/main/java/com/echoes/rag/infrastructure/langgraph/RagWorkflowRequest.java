package com.echoes.rag.infrastructure.langgraph;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * RAG 工作流请求
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RagWorkflowRequest {

    /**
     * 查询文本
     */
    private String query;

    /**
     * Turn ID（用于幂等性）
     */
    private String turnId;

    /**
     * 会话 ID
     */
    private String conversationId;

    /**
     * 知识库 ID 列表
     */
    private List<String> kbIds;

    /**
     * 返回数量
     */
    private Integer topK;

    /**
     * 是否流式输出
     */
    private Boolean stream;
}
