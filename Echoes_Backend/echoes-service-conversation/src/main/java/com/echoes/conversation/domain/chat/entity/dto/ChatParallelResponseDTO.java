package com.echoes.conversation.domain.chat.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "并行对话+语音响应")
public class ChatParallelResponseDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "完整回复文本")
    private String reply;

    @Schema(description = "分句及对应音频")
    private List<SentenceDTO> sentences;

    @Schema(description = "分句数量")
    private Integer count;
}


