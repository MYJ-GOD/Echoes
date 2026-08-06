package com.echoes.rag.domain.knowledge.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 知识库实体
 */
@Data
@TableName("knowledge_base")
public class KnowledgeBase {

    /**
     * 知识库 ID
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String kbId;

    /**
     * 知识库名称
     */
    private String name;

    /**
     * 描述
     */
    private String description;

    /**
     * 所有者用户 ID
     */
    private String ownerUserId;

    /**
     * 可见性
     */
    private String visibility;

    /**
     * 状态
     */
    private String status;

    /**
     * 配置
     */
    private String config;

    /**
     * 是否删除
     */
    @TableLogic
    private Integer isDeleted;

    /**
     * 删除时间
     */
    private LocalDateTime deletedAt;

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
