package com.echoes.exception;

import com.echoes.enumeration.BaseEnum;
import lombok.EqualsAndHashCode;

import java.io.Serial;

/**
 * 业务异常类
 * 用于处理业务逻辑中的异常情况
 */
@EqualsAndHashCode(callSuper = true)
public class BusinessException extends BaseException {

    @Serial
    private static final long serialVersionUID = 221477430191313484L;

    private static final int DEFAULT_ERROR_CODE = 500;

    public BusinessException(String message) {
        super(DEFAULT_ERROR_CODE, message);
    }

    public BusinessException(Integer code, String message) {
        super(code, message);
    }

    public <E extends Enum<E> & BaseEnum> BusinessException(E baseEnum) {
        super(baseEnum.getCode(), baseEnum.getMessage());
    }
}

