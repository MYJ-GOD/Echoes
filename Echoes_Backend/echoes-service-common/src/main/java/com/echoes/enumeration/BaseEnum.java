package com.echoes.enumeration;

/**
 * 基础枚举接口
 * 提供统一的枚举访问方式
 */
public interface BaseEnum {
    /**
     * 获取枚举的编码
     * @return 枚举编码（整数类型）
     */
    int getCode();

    /**
     * 获取枚举的消息描述
     * @return 枚举的描述信息
     */
    String getMessage();
}
