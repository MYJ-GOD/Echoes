package com.echoes.conversation.domain.chat.client.feign;

import com.echoes.conversation.common.result.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Slf4j
@Component
public class UserServiceClientFallback implements UserServiceClient {

    @Override
    public Result<?> login(String name, String password) {
        log.error("User service unavailable during login fallback");
        return Result.error("User service is temporarily unavailable");
    }

    @Override
    public Result<?> getUserById(String id) {
        log.error("User service unavailable during getUserById fallback, userId={}", id);
        return Result.error("User service is temporarily unavailable");
    }

    @Override
    public Result<Boolean> validateToken(String token) {
        log.error("User service unavailable during validateToken fallback");
        return Result.success(false);
    }
}