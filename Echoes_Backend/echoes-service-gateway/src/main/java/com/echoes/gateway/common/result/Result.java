package com.echoes.gateway.common.result;

import java.io.Serial;
import java.io.Serializable;

/**
 * 统一返回结果类
 * 用于 API 响应的标准化封装
 *
 * @param <T> 数据类型
 */
public class Result<T> implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private Integer code;
    private String msg;
    private T data;
    private Long timestamp;

    public Integer getCode() {
        return code;
    }

    public void setCode(Integer code) {
        this.code = code;
    }

    public String getMsg() {
        return msg;
    }

    public void setMsg(String msg) {
        this.msg = msg;
    }

    public T getData() {
        return data;
    }

    public void setData(T data) {
        this.data = data;
    }

    public Long getTimestamp() {
        return timestamp;
    }

    public void setTimestamp(Long timestamp) {
        this.timestamp = timestamp;
    }

    public static <T> Result<T> success() {
        Result<T> result = new Result<>();
        result.code = 1;
        result.msg = "OK";
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public static <T> Result<T> success(T data) {
        Result<T> result = new Result<>();
        result.code = 1;
        result.msg = "OK";
        result.data = data;
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public static <T> Result<T> success(String msg) {
        Result<T> result = new Result<>();
        result.code = 1;
        result.msg = msg;
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public static <T> Result<T> success(String msg, T data) {
        Result<T> result = new Result<>();
        result.code = 1;
        result.msg = msg;
        result.data = data;
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public static <T> Result<T> error(String msg) {
        Result<T> result = new Result<>();
        result.code = 0;
        result.msg = msg;
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public static <T> Result<T> error(Integer code, String msg) {
        Result<T> result = new Result<>();
        result.code = code;
        result.msg = msg;
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public static <T> Result<T> error(Integer code, String msg, T data) {
        Result<T> result = new Result<>();
        result.code = code;
        result.msg = msg;
        result.data = data;
        result.timestamp = System.currentTimeMillis();
        return result;
    }

    public boolean isSuccess() {
        return this.code != null && this.code == 1;
    }
}
