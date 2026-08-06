package com.echoes.gateway.config;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.echoes.gateway.domain.gateway.entity.dto.ErrorResponseDTO;

/**
 * Gateway 全局异常处理器
 *
 * 注意：Spring Cloud Gateway 是 WebFlux 应用，不支持 Servlet 相关的异常（如 MultipartException）
 * Gateway 的异常处理主要通过 GlobalFilter 实现，此处理器仅用于处理 Gateway 自身的异常
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 错误码定义
     */
    private static final class ErrorCode {
        private static final int PARAM_ERROR = 400;
        private static final int SERVICE_ERROR = 500;
        private static final int SYSTEM_ERROR = 500;
    }

    /**
     * 处理参数异常
     *
     * @param e 参数异常
     * @return 错误响应
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponseDTO> handleIllegalArgumentException(IllegalArgumentException e) {
        log.warn("参数异常: {}", e.getMessage());

        ErrorResponseDTO errorResponse = new ErrorResponseDTO(false, "参数错误", e.getMessage(), System.currentTimeMillis());
        return ResponseEntity.badRequest().body(errorResponse);
    }

    /**
     * 处理运行时异常
     *
     * @param e 运行时异常
     * @return 错误响应
     */
    @ExceptionHandler(RuntimeException.class)
    public ResponseEntity<ErrorResponseDTO> handleRuntimeException(RuntimeException e) {
        log.error("运行时异常: {}", e.getMessage(), e);

        ErrorResponseDTO errorResponse = new ErrorResponseDTO(false, "服务异常", "服务暂时不可用，请稍后重试", System.currentTimeMillis());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
    }

    /**
     * 处理所有其他异常
     *
     * @param e 异常
     * @return 错误响应
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponseDTO> handleException(Exception e) {
        log.error("未知异常: {}", e.getMessage(), e);

        ErrorResponseDTO errorResponse = new ErrorResponseDTO(false, "系统异常", "系统发生未知错误，请联系管理员", System.currentTimeMillis());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorResponse);
    }
}

