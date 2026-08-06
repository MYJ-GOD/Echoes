package com.echoes.conversation.domain.chat.client.feign;

import com.echoes.conversation.config.FeignConfig;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;

import java.util.UUID;

/**
 * 语音服务用户默认音色 Feign 客户端
 * 用于调用 echoes-service-voice 服务的用户默认音色查询接口
 *
 * 使用场景：
 * - 获取用户级默认音色
 * - 在会话没有设置默认音色时，回退到用户级默认音色
 */
@FeignClient(
        name = "echoes-service-voice",
        path = "/internal/voice",
        configuration = FeignConfig.class
)
public interface VoiceServiceUserDefaultClient {

    /**
     * 获取用户默认音色
     *
     * @param userId 用户 ID
     * @return 用户默认音色资产 ID，如果未设置则返回 404
     */
    @GetMapping("/users/{userId}/default-voice")
    ResponseEntity<UUID> getUserDefaultVoice(@PathVariable("userId") UUID userId);
}
