package com.echoes.rag.domain.knowledge.enums;

/**
 * 知识库状态枚举
 */
public enum KnowledgeBaseStatus {
    /**
     * 激活 - 正常使用中
     */
    ACTIVE("ACTIVE"),

    /**
     * 索引中 - 正在构建向量索引
     */
    INDEXING("INDEXING"),

    /**
     * 禁用 - 暂停使用
     */
    DISABLED("DISABLED");

    private final String code;

    KnowledgeBaseStatus(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    /**
     * 根据代码值获取枚举
     */
    public static KnowledgeBaseStatus fromCode(String code) {
        for (KnowledgeBaseStatus status : values()) {
            if (status.code.equals(code)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown status code: " + code);
    }

    /**
     * 判断是否是有效的状态代码
     */
    public static boolean isValidCode(String code) {
        if (code == null) {
            return false;
        }
        for (KnowledgeBaseStatus status : values()) {
            if (status.code.equals(code)) {
                return true;
            }
        }
        return false;
    }
}
