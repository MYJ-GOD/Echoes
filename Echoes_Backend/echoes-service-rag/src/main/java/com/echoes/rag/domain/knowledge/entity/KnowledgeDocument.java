package com.echoes.rag.domain.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识文档实体
 */
@Data
@TableName("knowledge_document")
public class KnowledgeDocument {

    /**
     * 文档 ID
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String docId;

    /**
     * 知识库 ID
     */
    private String kbId;

    /**
     * 文档标题
     */
    private String title;

    /**
     * 内容类型
     */
    private String contentType;

    /**
     * 来源 URL
     */
    private String sourceUrl;

    /**
     * 存储键
     */
    private String storageKey;

    /**
     * 字数
     */
    private Integer wordCount;

    /**
     * 状态
     */
    private String status;

    /**
     * 元数据
     */
    private String metadata;

    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updateTime;
}
