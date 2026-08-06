package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 消息 DTO，用于替代 Map<String,String> 表示的消息
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "聊天消息")
public class MessageDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "role 不能为空")
    @Schema(description = "消息角色，例如 user/system/assistant", requiredMode = Schema.RequiredMode.REQUIRED)
    private String role;

    @NotBlank(message = "content 不能为空")
    @Schema(description = "消息内容", requiredMode = Schema.RequiredMode.REQUIRED)
    private String content;
}


