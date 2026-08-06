package com.echoes.conversation.domain.chat.enums;

import lombok.Getter;

/**
 * 会话状态枚举
 * @author echoes
 */
@Getter
public enum SessionStatus {
    ACTIVE("active", "活跃"),
    ARCHIVED("archived", "已归档");

    private final String code;
    private final String desc;

    SessionStatus(String code, String desc) {
        this.code = code;
        this.desc = desc;
    }
}

