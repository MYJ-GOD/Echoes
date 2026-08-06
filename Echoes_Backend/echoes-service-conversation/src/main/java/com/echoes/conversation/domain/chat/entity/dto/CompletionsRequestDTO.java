package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

/**
 * 完整对话请求 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "完整对话请求")
public class CompletionsRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotEmpty(message = "messages 不能为空")
    @Valid
    @Schema(description = "消息列表", requiredMode = Schema.RequiredMode.REQUIRED)
    private List<MessageDTO> messages;

    @Schema(description = "温度参数")
    private Double temperature;

    @Schema(description = "top_p 参数")
    private Double top_p;

    @Schema(description = "最大 token 数")
    private Integer max_tokens;
}


