package com.echoes.voice.common.exception;

import com.echoes.exception.BaseException;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import lombok.Getter;

import java.io.Serial;

/**
 * 语音服务异常类
 * 用于抛出语音服务相关的业务异常
 */
@Getter
public class VoiceServiceException extends BaseException {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 错误枚举
     */
    private final VoiceErrorEnum errorEnum;

    public VoiceServiceException(VoiceErrorEnum errorEnum) {
        super(errorEnum.getCode(), errorEnum.getMessage());
        this.errorEnum = errorEnum;
    }

    public VoiceServiceException(VoiceErrorEnum errorEnum, String message) {
        super(errorEnum.getCode(), message);
        this.errorEnum = errorEnum;
    }

    public VoiceServiceException(VoiceErrorEnum errorEnum, String message, Throwable cause) {
        super(errorEnum.getCode(), message, cause);
        this.errorEnum = errorEnum;
    }

    public VoiceServiceException(VoiceErrorEnum errorEnum, Throwable cause) {
        super(errorEnum.getCode(), errorEnum.getMessage(), cause);
        this.errorEnum = errorEnum;
    }
}
