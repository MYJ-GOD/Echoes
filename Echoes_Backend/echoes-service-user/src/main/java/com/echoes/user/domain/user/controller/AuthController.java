package com.echoes.user.domain.user.controller;

import com.echoes.user.common.constants.LogMessageConstant;
import com.echoes.user.common.result.Result;
import com.echoes.user.domain.user.entity.dto.UserLoginDTO;
import com.echoes.user.domain.user.entity.dto.UserRegisterDTO;
import com.echoes.user.domain.user.entity.vo.UserLoginVO;
import com.echoes.user.domain.user.entity.vo.UserVO;
import com.echoes.user.domain.user.service.IAuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 认证控制器 (v3 无密码版)
 * 提供用户登录、注册、登出、Token验证等接口
 */
@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
@Tag(name = "认证管理", description = "用户认证相关接口")
public class AuthController {

    private final IAuthService authService;

    /**
     * 用户登录
     *
     * @param loginDTO 登录参数（手机号）
     * @return 登录结果（Token和用户信息）
     */
    @PostMapping("/auth/login")
    @Operation(summary = "用户登录", description = "手机号一键登录")
    public Result<UserLoginVO> login(@Valid @RequestBody UserLoginDTO loginDTO) {
        UserLoginVO loginVO = authService.login(loginDTO);
        return Result.success(loginVO);
    }

    /**
     * 用户注册
     *
     * @param registerDTO 注册参数（手机号、用户名）
     * @return 注册结果（Token和用户信息）
     */
    @PostMapping("/auth/register")
    @Operation(summary = "用户注册", description = "注册新用户(手机号+用户名)")
    public Result<UserLoginVO> register(@Valid @RequestBody UserRegisterDTO registerDTO) {
        UserLoginVO loginVO = authService.register(registerDTO);
        return Result.success(loginVO);
    }

    /**
     * 用户登出
     *
     * @param authorization Authorization头
     * @return 操作结果
     */
    @PostMapping("/auth/logout")
    @Operation(summary = "用户登出", description = "登出并注销Token")
    public Result<Void> logout(@RequestHeader("Authorization") String authorization) {
        String token = extractToken(authorization);
        authService.logout(token);
        return Result.success();
    }

    /**
     * 验证Token
     *
     * @param token JWT Token
     * @return Token是否有效
     */
    @PostMapping("/auth/validate")
    @Operation(summary = "验证Token", description = "验证JWT Token是否有效（网关调用）")
    public Result<Boolean> validateToken(@RequestParam("token") String token) {
        boolean valid = authService.validateToken(token);
        return Result.success(valid);
    }

    /**
     * 刷新Token
     *
     * @param authorization Authorization头
     * @return 新的Token
     */
    @PostMapping("/auth/refresh")
    @Operation(summary = "刷新Token", description = "刷新JWT Token")
    public Result<String> refreshToken(@RequestHeader("Authorization") String authorization) {
        String token = extractToken(authorization);
        String newToken = authService.refreshToken(token);
        return Result.success(newToken);
    }

    /**
     * 获取当前用户信息
     *
     * @param authorization Authorization头
     * @return 当前登录用户信息
     */
    @GetMapping("/auth/current")
    @Operation(summary = "获取当前用户信息", description = "根据Token获取当前登录用户信息")
    public Result<UserVO> getCurrentUser(@RequestHeader("Authorization") String authorization) {
        String token = extractToken(authorization);
        UserVO userVO = authService.getCurrentUser(token);
        return Result.success(userVO);
    }

    /**
     * 提取实际token（去除Bearer前缀）
     *
     * @param token 原始token字符串
     * @return 去除前缀后的token
     */
    private String extractToken(String token) {
        if (token != null && token.startsWith(LogMessageConstant.BEARER_PREFIX)) {
            return token.substring(LogMessageConstant.BEARER_PREFIX_LENGTH);
        }
        return token;
    }
}
