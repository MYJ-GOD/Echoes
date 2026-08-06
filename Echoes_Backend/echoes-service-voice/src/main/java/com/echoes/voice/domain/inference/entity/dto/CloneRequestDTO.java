package com.echoes.voice.domain.inference.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.web.multipart.MultipartFile;

import java.io.Serial;
import java.io.Serializable;

/**
 * 语音克隆请求DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "语音克隆请求")
public class CloneRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "参考音频文件", requiredMode = Schema.RequiredMode.REQUIRED)
    private MultipartFile promptWav;

    @NotBlank(message = "参考文本不能为空")
    @Schema(description = "参考音频对应的文本内容", requiredMode = Schema.RequiredMode.REQUIRED)
    private String promptText;

    @NotBlank(message = "合成文本不能为空")
    @Schema(description = "要合成的文本内容", requiredMode = Schema.RequiredMode.REQUIRED)
    private String ttsText;

    @Schema(description = "说话人名称（可选，默认：custom_speaker）")
    private java.util.UUID userId;

private String speakerName;
}