package com.echoes.voice.domain.voice.enums;

import lombok.Getter;

/**
 * 声音类型枚举
 * 定义声音的来源类型
 */
@Getter
public enum VoiceType {
    /**
     * 自定义音色
     */
    CUSTOM("custom", "自定义"),

    /**
     * 系统预设音色
     */
    SYSTEM("system", "系统");

    private final String code;
    private final String desc;

    VoiceType(String code, String desc) {
        this.code = code;
        this.desc = desc;
    }
}
