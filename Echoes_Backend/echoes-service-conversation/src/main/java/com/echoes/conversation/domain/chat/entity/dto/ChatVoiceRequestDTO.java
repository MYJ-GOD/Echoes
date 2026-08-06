package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 聊天 + 语音请求 DTO（简化版）
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "聊天并合成语音请求")
public class ChatVoiceRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "message 参数不能为空")
    @Schema(description = "用户消息", requiredMode = Schema.RequiredMode.REQUIRED)
    private String message;

    @Schema(description = "语音音色名称，默认 default")
    private String voiceName;
}


