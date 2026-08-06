package com.echoes.voice.domain.voice.enums;

import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 语音流式事件类型枚举
 * 用于标识流式响应中的事件类型
 * 
 * 注意：此枚举不实现 BaseEnum，因为事件类型是字符串类型，不是错误码
 */
@Getter
@AllArgsConstructor
public enum VoiceStreamEventTypeEnum {

    /**
     * 文本事件
     * 用于传输文本片段
     */
    TEXT("text", "文本事件"),

    /**
     * 音频块事件
     * 用于传输音频数据块
     */
    AUDIO_CHUNK("audio_chunk", "音频块事件"),

    /**
     * 音频句子事件
     * 用于传输完整句子的音频
     */
    AUDIO("audio", "音频句子事件"),

    /**
     * 结束事件
     * 表示流式传输结束
     */
    END("end", "结束事件"),

    /**
     * 错误事件
     * 表示发生错误
     */
    ERROR("error", "错误事件");

    /**
     * 事件类型代码（字符串类型）
     */
    private final String code;

    /**
     * 事件类型描述
     */
    private final String message;

    /**
     * 根据代码获取枚举
     *
     * @param code 事件类型代码
     * @return 对应的枚举，如果不存在则返回 null
     */
    public static VoiceStreamEventTypeEnum fromCode(String code) {
        if (code == null) {
            return null;
        }
        for (VoiceStreamEventTypeEnum type : values()) {
            if (type.getCode().equals(code)) {
                return type;
            }
        }
        return null;
    }

    /**
     * 判断是否为有效的事件类型
     *
     * @param code 事件类型代码
     * @return 是否为有效的事件类型
     */
    public static boolean isValid(String code) {
        return fromCode(code) != null;
    }
}
