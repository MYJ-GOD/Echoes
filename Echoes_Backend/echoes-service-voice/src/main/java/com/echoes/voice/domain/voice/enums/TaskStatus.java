package com.echoes.voice.domain.voice.enums;

import lombok.Getter;

/**
 * 训练任务状态枚举
 * 数据库存储枚举名称（小写）
 */
@Getter
public enum TaskStatus {
    /**
     * 待处理
     */
    PENDING,
    /**
     * 训练中
     */
    TRAINING,
    /**
     * 成功
     */
    SUCCESS,
    /**
     * 失败
     */
    FAILED,
    /**
     * 已取消
     */
    CANCELLED;

    /**
     * 根据code查找枚举（兼容大小写）
     */
    public static TaskStatus fromCode(String code) {
        if (code == null || code.isBlank()) {
            return null;
        }
        for (TaskStatus status : values()) {
            if (status.name().equalsIgnoreCase(code)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown status code: " + code);
    }
}
