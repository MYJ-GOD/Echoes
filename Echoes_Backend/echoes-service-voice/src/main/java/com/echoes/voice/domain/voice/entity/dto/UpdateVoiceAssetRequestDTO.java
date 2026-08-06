package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.util.List;
import java.util.UUID;

/**
 * 更新音色资产请求DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "更新音色资产请求")
public class UpdateVoiceAssetRequestDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "音色名称")
    private String name;

    @Schema(description = "角色标签: father/mother/friend/child/partner/self/other")
    private String role;

    @Schema(description = "标签列表 (如: [\"温柔\", \"怀旧\"])")
    private List<String> tags;
}

