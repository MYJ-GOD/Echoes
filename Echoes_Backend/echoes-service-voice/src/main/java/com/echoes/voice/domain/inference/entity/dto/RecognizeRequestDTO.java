package com.echoes.voice.domain.inference.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.web.multipart.MultipartFile;

import java.io.Serial;
import java.io.Serializable;

/**
 * 语音识别请求DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "语音识别请求")
public class RecognizeRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "要识别的音频文件", requiredMode = Schema.RequiredMode.REQUIRED)
    private MultipartFile audioFile;
}