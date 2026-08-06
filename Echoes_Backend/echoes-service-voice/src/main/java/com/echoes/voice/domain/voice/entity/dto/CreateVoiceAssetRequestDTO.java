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
import java.util.List;
import java.util.UUID;

/**
 * 创建音色资产请求DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "创建音色资产请求")
public class CreateVoiceAssetRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "参考音频ID不能为空")
    @Schema(description = "参考音频ID (refId)", requiredMode = Schema.RequiredMode.REQUIRED)
    private String refId;

    @NotBlank(message = "音色名称不能为空")
    @Schema(description = "音色名称", requiredMode = Schema.RequiredMode.REQUIRED)
    private String name;

    @NotNull(message = "角色标签不能为空")
    @Schema(description = "角色标签: father/mother/friend/child/partner/self/other", requiredMode = Schema.RequiredMode.REQUIRED)
    private String role;

    @Schema(description = "标签列表 (如: [\"温柔\", \"怀旧\"])")
    private List<String> tags;

    @Schema(description = "是否设为默认音色")
    private Boolean setAsDefault = false;
}

