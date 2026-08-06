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
@Schema(description = "文本合成请求")
public class SynthesizeTextRequestDTO implements Serializable {
    @Serial
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "text 不能为空")
    @Schema(description = "要合成的文本", requiredMode = Schema.RequiredMode.REQUIRED)
    private String text;

    @Schema(description = "音色名称")
    private String voiceName;
}
