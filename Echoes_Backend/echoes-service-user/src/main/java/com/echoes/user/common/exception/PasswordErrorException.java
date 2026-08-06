package com.echoes.user.common.exception;

import com.echoes.user.common.constants.ErrorCodeConstant;
import com.echoes.user.common.constants.MessageConstant;
import com.echoes.exception.BaseException;

import java.io.Serial;

/**
 * 密码错误异常
 */
public class PasswordErrorException extends BaseException {

    @Serial
    private static final long serialVersionUID = 1L;

    public PasswordErrorException() {
        super(ErrorCodeConstant.PASSWORD_ERROR, MessageConstant.PASSWORD_ERROR);
    }

    public PasswordErrorException(String message) {
        super(ErrorCodeConstant.PASSWORD_ERROR, message);
    }
}
