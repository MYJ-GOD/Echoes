package com.echoes.voice.domain.voice.entity.dto.query;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

/**
 * 音色列表查询请求
 */
@Data
public class VoiceListQueryRequest {

    @Parameter(description = "状态筛选: creating/ready/failed")
    private String status;

    @Parameter(description = "角色筛选: father/mother/friend/child/partner/self/other")
    private String role;

    @Parameter(description = "页码")
    private Integer pageNum = 1;

    @Parameter(description = "每页数量")
    private Integer pageSize = 20;

    @Parameter(description = "用户ID")
    private String userId;
}

