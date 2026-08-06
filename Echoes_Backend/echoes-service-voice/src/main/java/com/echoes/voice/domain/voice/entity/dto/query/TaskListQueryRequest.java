package com.echoes.voice.domain.voice.entity.dto.query;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

/**
 * 任务列表查询请求
 */
@Data
public class TaskListQueryRequest {

    @Parameter(description = "状态筛选: pending/training/success/failed")
    private String status;

    @Parameter(description = "页码")
    private Integer pageNum = 1;

    @Parameter(description = "每页数量")
    private Integer pageSize = 20;

    @Parameter(description = "用户ID")
    private String userId;
}

