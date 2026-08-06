package com.echoes.voice.domain.inference.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 语音合成响应VO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "语音合成响应")
public class SynthesizeResponseVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "是否成功")
    private Boolean success;

    @Schema(description = "生成的音频数据（base64编码）")
    private String audioData;

    @Schema(description = "音频时长（秒）")
    private Double durationSeconds;

    @Schema(description = "使用的音色名称")
    private String voiceName;
}