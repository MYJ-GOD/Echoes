package com.echoes.user.domain.user.enums;

import lombok.Getter;

/**
 * 用户状态枚举
 * 定义用户账号的可用状态
 */
@Getter
public enum UserStatus {
    /**
     * 活跃状态
     */
    ACTIVE("active", "活跃"),

    /**
     * 已封禁状态
     */
    BANNED("banned", "已封禁"),

    /**
     * 未激活状态
     */
    INACTIVE("inactive", "未激活");

    private final String code;
    private final String desc;

    UserStatus(String code, String desc) {
        this.code = code;
        this.desc = desc;
    }
}

