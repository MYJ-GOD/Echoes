package com.echoes.voice.domain.voice.entity.dto.query;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

/**
 * 音色资产任务列表查询请求
 */
@Data
public class AssetTasksQueryRequest {

    @Parameter(description = "音色资产ID", required = true)
    private String voiceAssetId;

    @Parameter(description = "用户ID")
    private String userId;
}

