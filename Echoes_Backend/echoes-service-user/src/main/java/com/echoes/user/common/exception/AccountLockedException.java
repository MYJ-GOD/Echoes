package com.echoes.user.common.exception;

import com.echoes.user.common.constants.ErrorCodeConstant;
import com.echoes.user.common.constants.MessageConstant;
import com.echoes.exception.BaseException;

import java.io.Serial;

/**
 * 账号被锁定异常
 */
public class AccountLockedException extends BaseException {

    @Serial
    private static final long serialVersionUID = 1L;

    public AccountLockedException() {
        super(ErrorCodeConstant.ACCOUNT_LOCKED, MessageConstant.ACCOUNT_LOCKED);
    }

    public AccountLockedException(String message) {
        super(ErrorCodeConstant.ACCOUNT_LOCKED, message);
    }
}
