package com.echoes.voice.domain.inference.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 语音合成（refId）请求DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "语音合成（refId）请求")
public class SynthesizeRefRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "参考音色ID不能为空")
    @Schema(description = "参考音色ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private String refId;

    @NotBlank(message = "合成文本不能为空")
    @Schema(description = "要合成的文本内容", requiredMode = Schema.RequiredMode.REQUIRED)
    private String text;

    @Schema(description = "音色名称（可选）")
    private String voiceName;
}