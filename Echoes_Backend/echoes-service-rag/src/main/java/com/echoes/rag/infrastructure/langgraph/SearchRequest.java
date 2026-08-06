package com.echoes.rag.infrastructure.langgraph;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 搜索请求
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SearchRequest {

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
}
