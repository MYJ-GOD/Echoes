package com.echoes.user.common.exception;

import com.echoes.user.common.constants.ErrorCodeConstant;
import com.echoes.user.common.constants.MessageConstant;
import com.echoes.exception.BaseException;

import java.io.Serial;

/**
 * 密码修改失败异常
 */
public class PasswordEditFailedException extends BaseException {

    @Serial
    private static final long serialVersionUID = 1L;

    public PasswordEditFailedException() {
        super(ErrorCodeConstant.OPERATION_NOT_ALLOWED, MessageConstant.PASSWORD_EDIT_FAILED);
    }

    public PasswordEditFailedException(String message) {
        super(ErrorCodeConstant.OPERATION_NOT_ALLOWED, message);
    }
}
