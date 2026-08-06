package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

import java.util.UUID;

/**
 * 授权操作请求
 */
@Data
public class GrantOperationRequest {

    @Parameter(description = "授权ID", required = true)
    private UUID grantId;

    @Parameter(description = "用户ID")
    private UUID userId;
}

