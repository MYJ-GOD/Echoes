package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.domain.chat.application.ChatStreamApplicationService;
import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Flux;

/**
 * 流式对话 + 语音合成控制器
 */
@RestController
@RequestMapping("/conversation")
@RequiredArgsConstructor
@Validated
public class StreamChatVoiceController {

    private final ChatStreamApplicationService chatStreamApplicationService;

    /**
     * 新版全双工流式对话接口
     */
    @PostMapping(value = "/chat-stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> streamChat(@Validated @RequestBody ChatRequestDTO request) {
        return chatStreamApplicationService.streamChat(request);
    }
}
