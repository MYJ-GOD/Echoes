package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

import java.util.UUID;

/**
 * 权限检查请求
 */
@Data
public class PermissionCheckRequest {

    @Parameter(description = "音色资产ID", required = true)
    private UUID voiceAssetId;

    @Parameter(description = "用户ID")
    private UUID userId;
}

