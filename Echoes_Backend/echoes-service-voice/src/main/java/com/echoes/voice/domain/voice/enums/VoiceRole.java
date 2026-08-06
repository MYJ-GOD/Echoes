package com.echoes.voice.domain.voice.enums;

import lombok.Getter;

/**
 * 音色角色标签枚举
 * 
 * @author echoes
 */
@Getter
public enum VoiceRole {
    FATHER("father", "爸爸"),
    MOTHER("mother", "妈妈"),
    FRIEND("friend", "朋友"),
    CHILD("child", "孩子"),
    PARTNER("partner", "伴侣"),
    SELF("self", "自己"),
    OTHER("other", "其他");

    private final String code;
    private final String desc;

    VoiceRole(String code, String desc) {
        this.code = code;
        this.desc = desc;
    }

    /**
     * 根据code查找枚举
     */
    public static VoiceRole fromCode(String code) {
        for (VoiceRole role : values()) {
            if (role.code.equalsIgnoreCase(code)) {
                return role;
            }
        }
        throw new IllegalArgumentException("Unknown role code: " + code);
    }
}

