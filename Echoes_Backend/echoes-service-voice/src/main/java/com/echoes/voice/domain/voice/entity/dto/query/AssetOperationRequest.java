package com.echoes.voice.domain.voice.entity.dto.query;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

/**
 * 音色资产操作请求（删除、设置默认等）
 */
@Data
public class AssetOperationRequest {

    @Parameter(description = "音色资产ID", required = true)
    private String voiceAssetId;

    @Parameter(description = "用户ID")
    private String userId;
}

