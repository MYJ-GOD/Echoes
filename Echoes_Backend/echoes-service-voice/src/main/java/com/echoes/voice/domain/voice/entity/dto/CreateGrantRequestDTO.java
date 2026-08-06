package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "创建分享授权请求")
public class CreateGrantRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @NotNull(message = "音色资产ID不能为空")
    @Schema(description = "音色资产ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private UUID voiceAssetId;

    @NotNull(message = "被授权用户ID不能为空")
    @Schema(description = "被授权用户ID", requiredMode = Schema.RequiredMode.REQUIRED)
    private UUID granteeUserId;

    @NotNull(message = "权限不能为空")
    @Schema(description = "权限: USE/MANAGE", requiredMode = Schema.RequiredMode.REQUIRED)
    private String permission;

    @Schema(description = "过期时间（可选）")
    private LocalDateTime expiresAt;

    @Schema(description = "是否永久授权（true=永久；false/空=按expiresAt或默认30天）")
    private Boolean permanent;
}
