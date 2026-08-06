package com.echoes.voice.domain.voice.entity.dto.query;

import io.swagger.v3.oas.annotations.Parameter;
import lombok.Data;

/**
 * 任务操作请求（取消等）
 */
@Data
public class TaskOperationRequest {

    @Parameter(description = "任务ID", required = true)
    private String taskId;

    @Parameter(description = "用户ID")
    private String userId;
}

