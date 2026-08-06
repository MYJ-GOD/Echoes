package com.echoes.voice.domain.inference.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

/**
 * 语音克隆响应VO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "语音克隆响应")
public class CloneResponseVO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "是否成功")
    private Boolean success;

    @Schema(description = "生成的音频数据（base64编码）")
    private String audioData;

    @Schema(description = "说话人名称")
    private String speakerName;

    @Schema(description = "声音配置文件路径")
    private String voiceFile;

    @Schema(description = "声纹模型ID（数据库中的voice_id）")
    private String voiceId;
}