package com.echoes.voice.domain.voice.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 音色资产查询请求DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "音色资产查询请求")
public class VoiceAssetQueryDTO implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    @Schema(description = "状态筛选: creating/ready/failed")
    private String status;

    @Schema(description = "角色筛选: father/mother/friend/child/partner/self/other")
    private String role;

    @Schema(description = "是否只查询默认音色")
    private Boolean defaultOnly = false;

    @Schema(description = "是否包含收到的分享")
    private Boolean includeShared = false;

    @Schema(description = "页码 (从1开始)")
    private Integer pageNum = 1;

    @Schema(description = "每页数量")
    private Integer pageSize = 20;
}

