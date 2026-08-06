package com.echoes.user.common.constants;

public class ErrorCodeConstant {

    public static final int SUCCESS = 1;
    public static final int UNKNOWN_ERROR = 0;
    public static final int PARAM_ERROR = 400;
    public static final int UNAUTHORIZED = 401;
    public static final int FORBIDDEN = 403;
    public static final int NOT_FOUND = 404;
    public static final int INTERNAL_SERVER_ERROR = 500;
    public static final int SERVICE_UNAVAILABLE = 503;

    public static final int ACCOUNT_NOT_FOUND = 1001;
    public static final int PASSWORD_ERROR = 1002;
    public static final int ACCOUNT_LOCKED = 1003;
    public static final int ACCOUNT_ALREADY_EXISTS = 1004;
    public static final int USER_NOT_LOGIN = 1005;
    public static final int LOGIN_FAILED = 1006;
    public static final int TOKEN_INVALID = 1007;
    public static final int TOKEN_EXPIRED = 1008;
    public static final int TOKEN_REFRESH_FAILED = 1009;
    public static final int GET_CURRENT_USER_FAILED = 1010;

    public static final int DATA_NOT_FOUND = 2001;
    public static final int DATA_ALREADY_EXISTS = 2002;
    public static final int DELETION_NOT_ALLOWED = 2003;
    public static final int OPERATION_NOT_ALLOWED = 2004;

    public static final int UPLOAD_FAILED = 3001;
    public static final int FILE_TOO_LARGE = 3002;
    public static final int FILE_FORMAT_NOT_SUPPORTED = 3003;

    public static final int VALIDATION_FAILED = 4001;
    public static final int METHOD_NOT_ALLOWED = 4005;
    public static final int TOO_MANY_REQUESTS = 4029;

    private ErrorCodeConstant() {
    }
}
