package com.echoes.conversation.domain.chat.client.feign;

import com.echoes.conversation.common.result.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * UserServiceClient 的降级处理类
 * 当用户服务不可用时，提供兜底响应
 *
 * @author echoes
 */
@Slf4j
@Component
public class UserServiceClientFallback implements UserServiceClient {

    @Override
    public Result<?> login(String name, String password) {
        log.error("用户服务不可用，login 降级处理");
        return Result.error("用户服务暂时不可用，请稍后重试");
    }

    @Override
    public Result<?> getUserById(String id) {
        log.error("用户服务不可用，getUserById 降级处理，userId={}", id);
        return Result.error("用户服务暂时不可用，请稍后重试");
    }

    @Override
    public Result<Boolean> validateToken(String token) {
        log.error("用户服务不可用，validateToken 降级处理");
        // Token 验证降级：返回 false，让调用方按未登录处理
        return Result.success(false);
    }
}
