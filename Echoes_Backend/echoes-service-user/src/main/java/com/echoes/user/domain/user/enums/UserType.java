package com.echoes.user.domain.user.enums;

import com.echoes.enumeration.BaseEnum;
import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 用户类型枚举
 * 定义用户在系统中的角色类型
 */
@Getter
@AllArgsConstructor
public enum UserType implements BaseEnum {
    /**
     * 老人用户
     */
    ELDER(1, "老人"),

    /**
     * 儿童用户
     */
    CHILD(2, "儿童"),

    /**
     * 普通用户
     */
    NORMAL(3, "普通用户");

    private final int code;
    private final String description;

    @Override
    public String getMessage() {
        return description;
    }

    public static UserType fromCode(int code) {
        for (UserType type : values()) {
            if (type.getCode() == code) {
                return type;
            }
        }
        return null;
    }

    /**
     * 根据数据库存储的字符串名称获取枚举
     * @param name 数据库中的字符串值 (elder/child/normal)
     * @return 对应的枚举值
     */
    public static UserType fromName(String name) {
        if (name == null || name.isBlank()) {
            return null;
        }
        try {
            return valueOf(name.toUpperCase());
        } catch (IllegalArgumentException e) {
            return null;
        }
    }
}
