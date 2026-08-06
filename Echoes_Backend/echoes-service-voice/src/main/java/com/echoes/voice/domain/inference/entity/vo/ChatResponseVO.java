package com.echoes.voice.domain.inference.entity.vo;

import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatResponseVO {
    private String type; // "text", "audio", "error", "status"
    private String content; // Text content
    private byte[] audioData; // Audio content
    private Boolean isFinal;
    private String delta;
}