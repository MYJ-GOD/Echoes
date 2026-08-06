package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.po.ChatMessage;
import com.echoes.conversation.domain.chat.entity.vo.ChatResponseVO;
import com.echoes.conversation.domain.chat.service.IChatMessageService;
import org.springframework.data.redis.core.RedisTemplate;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.echoes.conversation.common.result.Result;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import com.echoes.utils.UuidUtils;

@Tag(name = "AI对话消息管理", description = "用于管理AI对话消息的API")
@RestController
@RequestMapping("/message")
@RequiredArgsConstructor
@Slf4j
public class ChatMessageController {

    private final IChatMessageService chatMessageService;
    @SuppressWarnings("unused")
    private final RedisTemplate<String, Object> redisTemplate;
    @SuppressWarnings("unused")
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 发送对话消息
     *
     * @param request 对话请求参数
     * @return 对话响应结果
     */
    @PostMapping("/send")
    public Result<ChatResponseVO> chat(@Valid @RequestBody ChatRequestDTO request) {
        ChatResponseVO response = chatMessageService.chat(request);
        return Result.success(response);
    }





    @GetMapping("/{id}")
    public Result<ChatMessage> getChatMessageById(
            @Parameter(name = "id", description = "消息ID", required = true) @PathVariable("id") String id
    ) {
        java.util.UUID uuid = UuidUtils.parseLenient(id);
        ChatMessage chatMessage = chatMessageService.getChatMessageById(uuid);
        return Result.success(chatMessage);
    }

    @PostMapping("/{id}/feedback")
    public Result<Boolean> feedbackMessage(
            @Parameter(name = "id", description = "消息ID", required = true) @PathVariable("id") String id,
            @Parameter(name = "feedback", description = "反馈类型: 1-有用, -1-无用", required = true) @RequestParam("feedback") Integer feedback
    ) {
        java.util.UUID uuid = UuidUtils.parseLenient(id);
        Boolean result = chatMessageService.feedbackMessage(uuid, feedback);
        return Result.success(result);
    }
}

