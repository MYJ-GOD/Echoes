package com.echoes.user.domain.user.enums;

import com.echoes.enumeration.BaseEnum;

/**
 * 日志消息枚举
 * 定义系统中常用的日志消息模板
 */
public enum LogMessageEnum implements BaseEnum {

    /**
     * 登录失败
     */
    LOGIN_FAILED(10003, "登录失败: {}"),

    /**
     * 账号不存在
     */
    ACCOUNT_NOT_FOUND(10004, "账号不存在 {}"),

    /**
     * 密码错误
     */
    PASSWORD_ERROR(10005, "密码错误: {}"),

    /**
     * 账号被锁定
     */
    ACCOUNT_LOCKED(10006, "账号被锁定 {}"),

    /**
     * 登录失败：账号状态异常
     */
    LOGIN_FAILED_STATUS_ERROR(20007, "登录失败: 账号状态异常 userId={}, status={}"),

    /**
     * 用户登录成功
     */
    USER_LOGIN_SUCCESS(20001, "用户登录成功: userId={}, name={}"),

    /**
     * 注册失败：手机号已存在
     */
    REGISTER_FAILED_PHONE_EXISTS(20009, "注册失败: 手机号已存在, phoneNumber={}");

    private final int code;
    private final String message;

    LogMessageEnum(int code, String message) {
        this.code = code;
        this.message = message;
    }

    @Override
    public int getCode() {
        return code;
    }

    @Override
    public String getMessage() {
        return message;
    }
}
