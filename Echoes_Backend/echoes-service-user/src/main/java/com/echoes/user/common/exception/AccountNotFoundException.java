package com.echoes.user.common.exception;

import com.echoes.user.common.constants.ErrorCodeConstant;
import com.echoes.user.common.constants.MessageConstant;
import com.echoes.exception.BaseException;

import java.io.Serial;

/**
 * 账号不存在异常
 */
public class AccountNotFoundException extends BaseException {

    @Serial
    private static final long serialVersionUID = 1L;

    public AccountNotFoundException() {
        super(ErrorCodeConstant.ACCOUNT_NOT_FOUND, MessageConstant.ACCOUNT_NOT_FOUND);
    }

    public AccountNotFoundException(String message) {
        super(ErrorCodeConstant.ACCOUNT_NOT_FOUND, message);
    }
}
