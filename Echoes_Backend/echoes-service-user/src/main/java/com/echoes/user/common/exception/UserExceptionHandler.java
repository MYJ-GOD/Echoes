package com.echoes.user.common.exception;

import com.echoes.user.common.constants.ErrorCodeConstant;
import com.echoes.user.domain.user.enums.LogMessageEnum;
import com.echoes.user.common.constants.LogMessageConstant;
import com.echoes.user.common.result.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import jakarta.validation.ConstraintViolationException;
import java.util.stream.Collectors;

/**
 * 用户服务全局异常处理器
 * 统一处理用户服务中的各类异常
 */
@Slf4j
@RestControllerAdvice
public class UserExceptionHandler {

    /**
     * 处理登录失败异常
     *
     * @param e 登录失败异常
     * @return 错误响应
     */
    @ExceptionHandler(LoginFailedException.class)
    public Result<Void> handleLoginFailedException(LoginFailedException e) {
        log.warn(LogMessageEnum.LOGIN_FAILED.getMessage(), e.getMessage());
        return Result.error(ErrorCodeConstant.LOGIN_FAILED, e.getMessage());
    }

    /**
     * 处理账号不存在异常
     *
     * @param e 账号不存在异常
     * @return 错误响应
     */
    @ExceptionHandler(AccountNotFoundException.class)
    public Result<Void> handleAccountNotFoundException(AccountNotFoundException e) {
        log.warn(LogMessageEnum.ACCOUNT_NOT_FOUND.getMessage(), e.getMessage());
        return Result.error(ErrorCodeConstant.ACCOUNT_NOT_FOUND, e.getMessage());
    }

    /**
     * 处理密码错误异常
     *
     * @param e 密码错误异常
     * @return 错误响应
     */
    @ExceptionHandler(PasswordErrorException.class)
    public Result<Void> handlePasswordErrorException(PasswordErrorException e) {
        log.warn(LogMessageEnum.PASSWORD_ERROR.getMessage(), e.getMessage());
        return Result.error(ErrorCodeConstant.PASSWORD_ERROR, e.getMessage());
    }

    /**
     * 处理账号锁定异常
     *
     * @param e 账号锁定异常
     * @return 错误响应
     */
    @ExceptionHandler(AccountLockedException.class)
    public Result<Void> handleAccountLockedException(AccountLockedException e) {
        log.warn(LogMessageEnum.ACCOUNT_LOCKED.getMessage(), e.getMessage());
        return Result.error(ErrorCodeConstant.ACCOUNT_LOCKED, e.getMessage());
    }

    /**
     * 处理密码修改失败异常
     *
     * @param e 密码修改失败异常
     * @return 错误响应
     */
    @ExceptionHandler(PasswordEditFailedException.class)
    public Result<Void> handlePasswordEditFailedException(PasswordEditFailedException e) {
        log.warn("密码修改失败: {}", e.getMessage());
        return Result.error(ErrorCodeConstant.OPERATION_NOT_ALLOWED, e.getMessage());
    }

    /**
     * 处理 @Valid 参数校验失败异常 (RequestBody binding)
     *
     * @param e 参数校验失败异常
     * @return 错误响应
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleMethodArgumentNotValid(MethodArgumentNotValidException e) {
        String msg = e.getBindingResult().getFieldErrors().stream()
                .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn(LogMessageConstant.PARAM_VALIDATION_FAILED, msg);
        return Result.error(ErrorCodeConstant.VALIDATION_FAILED, msg);
    }

    /**
     * 处理表单/绑定异常
     *
     * @param e 绑定异常
     * @return 错误响应
     */
    @ExceptionHandler(BindException.class)
    public Result<Void> handleBindException(BindException e) {
        String msg = e.getAllErrors().stream()
                .map(err -> err.getDefaultMessage())
                .collect(Collectors.joining("; "));
        log.warn(LogMessageConstant.PARAM_BIND_FAILED, msg);
        return Result.error(ErrorCodeConstant.VALIDATION_FAILED, msg);
    }

    /**
     * 处理单个参数的约束校验异常（如 @RequestParam/@PathVariable 校验）
     *
     * @param e 约束校验异常
     * @return 错误响应
     */
    @ExceptionHandler(ConstraintViolationException.class)
    public Result<Void> handleConstraintViolation(ConstraintViolationException e) {
        String msg = e.getConstraintViolations().stream()
                .map(cv -> cv.getMessage())
                .collect(Collectors.joining("; "));
        log.warn(LogMessageConstant.CONSTRAINT_VIOLATION_FAILED, msg);
        return Result.error(ErrorCodeConstant.VALIDATION_FAILED, msg);
    }

    /**
     * 处理无法解析的请求体（JSON 格式错误）
     *
     * @param e HTTP消息不可读异常
     * @return 错误响应
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public Result<Void> handleHttpMessageNotReadable(HttpMessageNotReadableException e) {
        log.warn(LogMessageConstant.HTTP_MESSAGE_NOT_READABLE, e.getMessage());
        return Result.error(ErrorCodeConstant.VALIDATION_FAILED, "请求体格式错误，请检查JSON格式");
    }
}
