package com.echoes.admin.domain.governance.entity.vo;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 失败分布总览 VO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "失败分布总览")
public class FailureOverviewVO {

    @Schema(description = "总 Turn 数")
    private int totalTurns;

    @Schema(description = "失败 Turn 数")
    private int failedTurns;

    @Schema(description = "失败率")
    private double failureRate;

    @Schema(description = "按错误码分组统计")
    private List<ErrorCodeStatistics> errorCodeStats;

    @Schema(description = "按错误阶段分组统计")
    private List<ErrorStageStatistics> errorStageStats;

    /**
     * 错误码统计
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ErrorCodeStatistics {
        @Schema(description = "错误码")
        private String errorCode;
        @Schema(description = "错误阶段")
        private String errorStage;
        @Schema(description = "数量")
        private int count;
        @Schema(description = "占比")
        private double percentage;
    }

    /**
     * 错误阶段统计
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ErrorStageStatistics {
        @Schema(description = "错误阶段")
        private String errorStage;
        @Schema(description = "数量")
        private int count;
        @Schema(description = "占比")
        private double percentage;
    }
}
