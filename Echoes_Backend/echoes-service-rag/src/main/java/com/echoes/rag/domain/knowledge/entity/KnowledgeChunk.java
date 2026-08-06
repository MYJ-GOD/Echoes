package com.echoes.rag.domain.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识片段实体
 */
@Data
@TableName("knowledge_chunk")
public class KnowledgeChunk {

    /**
     * 片段 ID
     */
    @TableId
    private String chunkId;

    /**
     * 文档 ID
     */
    private String docId;

    /**
     * 知识库 ID
     */
    private String kbId;

    /**
     * 片段索引
     */
    private Integer chunkIndex;

    /**
     * 内容
     */
    private String content;

    /**
     * Embedding 版本
     */
    private String embeddingVersion;

    /**
     * Qdrant 向量 ID
     */
    private String vectorId;

    /**
     * 元数据
     */
    private String metadata;

    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;
}
