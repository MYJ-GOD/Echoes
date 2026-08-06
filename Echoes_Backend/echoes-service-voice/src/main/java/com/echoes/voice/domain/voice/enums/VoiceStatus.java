package com.echoes.voice.domain.voice.enums;

import lombok.Getter;

/**
 * 声纹模型训练状态枚举
 * 数据库存储枚举名称（小写）
 */
@Getter
public enum VoiceStatus {
    /**
     * 训练中
     */
    TRAINING,
    /**
     * 就绪
     */
    READY,
    /**
     * 错误
     */
    ERROR,
    /**
     * 已删除
     */
    DELETED;

    /**
     * 根据code查找枚举（兼容大小写）
     */
    public static VoiceStatus fromCode(String code) {
        if (code == null || code.isBlank()) {
            return null;
        }
        for (VoiceStatus status : values()) {
            if (status.name().equalsIgnoreCase(code)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown status code: " + code);
    }
}
