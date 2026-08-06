package com.echoes.voice.domain.inference.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 语音识别响应VO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "语音识别响应")
public class RecognizeResponseVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "是否成功")
    private Boolean success;

    @Schema(description = "识别出的文本")
    private String recognizedText;

    @Schema(description = "原始文件名")
    private String filename;

    @Schema(description = "错误信息（如果失败）")
    private String error;
}