package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.domain.chat.service.IChatService;
import com.fasterxml.jackson.databind.JsonNode;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.validation.annotation.Validated;

/**
 * Expose lightweight AI model list endpoint for frontend consumption.
 * Keeps previous /api/chat/models compatibility.
 */
@Tag(name = "AI 模型", description = "列出可用的 AI 模型")
@RestController
@RequestMapping("/conversation")
@RequiredArgsConstructor
@Slf4j
@Validated
public class ChatModelController {

    private final IChatService chatService;

    @GetMapping("/models")
    public ResponseEntity<JsonNode> listModels() {
        /**
         * 列出可用 AI 模型的 JSON 列表
         * @return Http 200 + models JSON 或 500
         */
        try {
            JsonNode models = chatService.listModels();
            return ResponseEntity.ok(models);
        } catch (Exception e) {
            log.error("获取模型列表失败", e);
            return ResponseEntity.internalServerError().build();
        }
    }
}


