package com.echoes.conversation.common.constants;

import com.echoes.enumeration.BaseEnum;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor
public enum ErrorCode implements BaseEnum {
    SUCCESS(1, "success"),
    UNKNOWN_ERROR(0, "unknown error"),
    PARAM_ERROR(400, "parameter error"),
    UNAUTHORIZED(401, "unauthorized"),
    FORBIDDEN(403, "forbidden"),
    NOT_FOUND(404, "not found"),
    INTERNAL_SERVER_ERROR(500, "internal server error"),
    SERVICE_UNAVAILABLE(503, "service unavailable"),

    ACCOUNT_NOT_FOUND(1001, "account not found"),
    PASSWORD_ERROR(1002, "password error"),
    ACCOUNT_LOCKED(1003, "account locked"),
    ACCOUNT_ALREADY_EXISTS(1004, "account already exists"),
    USER_NOT_LOGIN(1005, "user not login"),
    LOGIN_FAILED(1006, "login failed"),
    TOKEN_INVALID(1007, "token invalid"),
    TOKEN_EXPIRED(1008, "token expired"),
    TOKEN_REFRESH_FAILED(1009, "token refresh failed"),
    GET_CURRENT_USER_FAILED(1010, "get current user failed"),

    DATA_NOT_FOUND(2001, "data not found"),
    DATA_ALREADY_EXISTS(2002, "data already exists"),
    DELETION_NOT_ALLOWED(2003, "deletion not allowed"),
    OPERATION_NOT_ALLOWED(2004, "operation not allowed"),

    UPLOAD_FAILED(3001, "upload failed"),
    FILE_TOO_LARGE(3002, "file too large"),
    FILE_FORMAT_NOT_SUPPORTED(3003, "file format not supported"),

    VALIDATION_FAILED(4001, "validation failed"),
    METHOD_NOT_ALLOWED(4005, "method not allowed"),
    TOO_MANY_REQUESTS(4029, "too many requests");

    private final int code;
    private final String message;
}
