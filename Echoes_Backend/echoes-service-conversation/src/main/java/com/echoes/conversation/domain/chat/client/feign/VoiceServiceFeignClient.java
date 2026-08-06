package com.echoes.conversation.domain.chat.client.feign;

import com.echoes.conversation.config.FeignConfig;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import com.echoes.conversation.domain.chat.entity.dto.SynthesizeTextRequestDTO;

/**
 * 语音服务 Feign 客户端（同步调用）
 * 用于调用 echoes-service-voice 服务的同步、非流式接口
 *
 * 【使用场景】
 * - 文本转语音（小文本，非实时）
 * - 音色信息查询
 * - 其他同步请求/响应式调用
 *
 * 【不适用场景】
 * - 流式响应（如 SSE、音频流）：请使用 {@link com.echoes.conversation.domain.chat.client.VoiceServiceWebClient}
 * - 需要背压控制的长连接：请使用 {@link com.echoes.conversation.domain.chat.client.VoiceServiceWebClient}
 * - 需要复杂错误处理/重试：请使用 {@link com.echoes.conversation.domain.chat.client.VoiceServiceWebClient}
 */
@FeignClient(
        name = "echoes-service-voice",
        path = "",
        configuration = FeignConfig.class
)
public interface VoiceServiceFeignClient {

    /**
     * 文本转语音（使用指定音色）
     *
     * @param request 请求参数，包含 text 和 voiceName
     * @return 音频字节数组（WAV 格式）
     *
     * 示例请求：
     * {
     *   "text": "要合成的文本",
     *   "voiceName": "音色名称"
     * }
     */
    @PostMapping(value = "/voice/inference/synthesize-text", consumes = "application/json")
    ResponseEntity<byte[]> synthesizeText(@RequestBody SynthesizeTextRequestDTO request);
}
