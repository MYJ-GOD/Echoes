package com.echoes.conversation.domain.chat.client.feign;

import com.echoes.conversation.config.FeignConfig;
import com.echoes.conversation.common.result.Result;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * 用户服务 Feign 客户端
 * 用于调用 echoes-service-user 服务的接口
 */
@FeignClient(
        name = "echoes-service-user",
        path = "/user",
        configuration = FeignConfig.class,
        fallback = UserServiceClientFallback.class
)
public interface UserServiceClient {

    /**
     * 用户登录
     *
     * @param name     用户名
     * @param password 密码
     * @return 登录结果
     */
    @PostMapping("/login")
    Result<?> login(@RequestParam("name") String name, @RequestParam("password") String password);

    /**
     * 根据 ID 获取用户信息
     * 示例方法，根据实际业务需求添加
     *
     * @param id 用户 ID
     * @return 用户信息
     */
    @GetMapping("/{id}")
    Result<?> getUserById(@PathVariable("id") String id);

    /**
     * 验证Token
     * 网关调用此接口验证JWT Token是否有效
     *
     * @param token JWT Token
     * @return 验证结果（true表示有效，false表示无效）
     */
    @PostMapping("/auth/validate")
    Result<Boolean> validateToken(@RequestParam("token") String token);

    // 可以根据实际业务需求继续添加其他方法
}
