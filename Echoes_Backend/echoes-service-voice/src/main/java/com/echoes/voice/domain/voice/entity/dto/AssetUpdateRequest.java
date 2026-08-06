package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

/**
 * 音色资产更新请求（包含路径参数和请求头）
 */
@Data
public class AssetUpdateRequest {

    @Parameter(description = "音色资产ID", required = true)
    private String voiceAssetId;

    @Parameter(description = "用户ID")
    private String userId;

    // UpdateVoiceAssetRequestDTO 的字段
    @Parameter(description = "音色名称")
    private String name;

    @Parameter(description = "角色")
    private String role;

    @Parameter(description = "标签列表")
    private String tags;
}

