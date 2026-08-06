package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 简单对话响应 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "简单对话响应")
public class SimpleChatResponseDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "回复文本")
    private String reply;
}


