package com.echoes.voice.domain.inference.entity.dto;

import lombok.Data;

@Data
public class ChatRequestDTO {
    private String message;
    private String sessionId;
    private String refAudioPath;
    private String refText;
    private boolean stream = true;
}