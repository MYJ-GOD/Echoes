package com.echoes.gateway.domain.gateway.entity.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class ErrorResponseDTO implements Serializable {
    @Serial
    private static final long serialVersionUID = 1L;

    private boolean success;
    private String error;
    private String message;
    private long timestamp;
}


