package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "简单对话请求")
public class SimpleChatRequestDTO implements Serializable {
    @Serial
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "message 不能为空")
    @Schema(description = "用户消息", requiredMode = Schema.RequiredMode.REQUIRED)
    private String message;
}


