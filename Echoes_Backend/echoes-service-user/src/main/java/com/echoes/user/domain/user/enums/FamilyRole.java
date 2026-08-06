package com.echoes.user.domain.user.enums;

import com.echoes.enumeration.BaseEnum;
import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 家庭成员角色枚举
 */
@Getter
@AllArgsConstructor
public enum FamilyRole implements BaseEnum {

    PARENT(1, "父母"),
    CHILD(2, "子女"),
    CAREGIVER(3, "照护者"),
    OTHER(4, "其他");

    private final int code;
    private final String description;

    @Override
    public String getMessage() {
        return description;
    }

    public static FamilyRole fromCode(int code) {
        for (FamilyRole role : values()) {
            if (role.getCode() == code) {
                return role;
            }
        }
        return null;
    }
}
