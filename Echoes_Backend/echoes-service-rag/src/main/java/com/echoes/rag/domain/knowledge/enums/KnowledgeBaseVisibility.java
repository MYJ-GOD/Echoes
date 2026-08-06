package com.echoes.rag.domain.knowledge.enums;

/**
 * 知识库可见性枚举
 */
public enum KnowledgeBaseVisibility {
    /**
     * 私有 - 仅所有者可访问
     */
    PRIVATE("PRIVATE"),

    /**
     * 共享 - 对特定用户共享
     */
    SHARED("SHARED"),

    /**
     * 公共 - 所有人可访问
     */
    PUBLIC("PUBLIC");

    private final String code;

    KnowledgeBaseVisibility(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }

    /**
     * 根据代码值获取枚举
     */
    public static KnowledgeBaseVisibility fromCode(String code) {
        for (KnowledgeBaseVisibility visibility : values()) {
            if (visibility.code.equals(code)) {
                return visibility;
            }
        }
        throw new IllegalArgumentException("Unknown visibility code: " + code);
    }

    /**
     * 判断是否是有效的可见性代码
     */
    public static boolean isValidCode(String code) {
        if (code == null) {
            return false;
        }
        for (KnowledgeBaseVisibility visibility : values()) {
            if (visibility.code.equals(code)) {
                return true;
            }
        }
        return false;
    }
}
