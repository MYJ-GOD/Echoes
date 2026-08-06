package com.echoes.user.common.exception;

import com.echoes.user.common.constants.ErrorCodeConstant;
import com.echoes.user.common.constants.MessageConstant;
import com.echoes.exception.BaseException;

import java.io.Serial;

/**
 * 登录失败异常
 */
public class LoginFailedException extends BaseException {

    @Serial
    private static final long serialVersionUID = 1L;

    public LoginFailedException() {
        super(ErrorCodeConstant.LOGIN_FAILED, MessageConstant.LOGIN_FAILED);
    }

    public LoginFailedException(String message) {
        super(ErrorCodeConstant.LOGIN_FAILED, message);
    }
}
