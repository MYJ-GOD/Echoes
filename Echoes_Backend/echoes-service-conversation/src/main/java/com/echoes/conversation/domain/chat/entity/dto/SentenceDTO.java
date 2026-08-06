package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "分句和对应音频")
public class SentenceDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "句子文本")
    private String text;

    @Schema(description = "base64 编码的音频")
    private String audio;
}


