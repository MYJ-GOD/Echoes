package com.echoes.voice.domain.voice.enums;

import lombok.Getter;

/**
 * 关系类型枚举
 * @author echoes
 */
@Getter
public enum RelationType {
    FATHER("father", "父亲"),
    MOTHER("mother", "母亲"),
    FRIEND("friend", "朋友"),
    CHILD("child", "孩子"),
    PARTNER("partner", "伴侣"),
    SELF("self", "自己"),
    OTHER("other", "其他");

    private final String code;
    private final String desc;

    RelationType(String code, String desc) {
        this.code = code;
        this.desc = desc;
    }
}
