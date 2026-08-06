package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.util.UUID;

/**
 * 创建训练任务请求DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "创建训练任务请求")
public class CreateTrainingTaskRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotNull(message = "音色资产ID不能为空")
    @Schema(description = "音色资产ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private UUID voiceAssetId;

    @NotBlank(message = "参考音频ID不能为空")
    @Schema(description = "参考音频ID (refId)", requiredMode = Schema.RequiredMode.REQUIRED)
    private String refId;

    @Schema(description = "OSS存储路径 (可选，不提供则通过refId查询)")
    private String storageKey;

    @Schema(description = "模型版本号 (默认1)")
    private Integer modelVersion = 1;

    @Schema(description = "自定义prompt (可选)")
    private String prompt;
}

