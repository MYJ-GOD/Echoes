package com.echoes.voice.domain.voice.controller;

import com.echoes.voice.domain.voice.service.IVoiceTrainingService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

/**
 * AI callback controller for voice training.
 */
@Tag(name = "AI回调接口", description = "AI 服务回调接口")
@RestController
@RequestMapping("/internal/voice/callback")
@RequiredArgsConstructor
@Slf4j
public class VoiceTrainingCallbackController {

    private final IVoiceTrainingService voiceTrainingService;

    @Operation(summary = "更新训练进度")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "更新成功"),
        @ApiResponse(responseCode = "400", description = "参数错误")
    })
    @PostMapping("/progress/{taskId}")
    public ResponseEntity<ResponseResult<Void>> updateProgress(
            @Parameter(description = "任务ID") @PathVariable("taskId") String taskId,
            @RequestBody ProgressCallbackRequest request) {
        try {
            UUID taskUuid = UUID.fromString(taskId);
            voiceTrainingService.updateProgress(taskUuid, request.getProgress());
            return ResponseEntity.ok(ResponseResult.success(null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ResponseResult.error("无效的任务ID格式"));
        } catch (Exception e) {
            log.error("更新训练进度异常: taskId={}", taskId, e);
            return ResponseEntity.internalServerError().body(ResponseResult.error("更新失败: " + e.getMessage()));
        }
    }

    @Operation(summary = "训练完成回调")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "处理成功"),
        @ApiResponse(responseCode = "400", description = "参数错误")
    })
    @PostMapping("/complete/success/{taskId}")
    public ResponseEntity<ResponseResult<Void>> completeSuccess(
            @Parameter(description = "任务ID") @PathVariable("taskId") String taskId,
            @RequestBody(required = false) SuccessCallbackRequest request) {
        try {
            UUID taskUuid = UUID.fromString(taskId);
            UUID voiceModelId = parseVoiceModelId(request != null ? request.getVoiceModelId() : null);
            String voiceIdExternal = request != null ? request.getVoiceIdExternal() : null;
            BigDecimal similarityScore = request != null ? request.getSimilarityScore() : null;
            String modelPath = request != null ? request.getModelPath() : null;

            voiceTrainingService.completeSuccess(taskUuid, voiceModelId, voiceIdExternal, similarityScore, modelPath);
            return ResponseEntity.ok(ResponseResult.success(null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ResponseResult.error("无效的任务ID格式"));
        } catch (Exception e) {
            log.error("训练完成回调异常: taskId={}", taskId, e);
            return ResponseEntity.internalServerError().body(ResponseResult.error("处理失败: " + e.getMessage()));
        }
    }

    @Operation(summary = "训练失败回调")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "处理成功"),
        @ApiResponse(responseCode = "400", description = "参数错误")
    })
    @PostMapping("/complete/failed/{taskId}")
    public ResponseEntity<ResponseResult<Void>> completeFailed(
            @Parameter(description = "任务ID") @PathVariable("taskId") String taskId,
            @RequestBody(required = false) FailedCallbackRequest request) {
        try {
            UUID taskUuid = UUID.fromString(taskId);
            String errorMessage = request != null ? request.getErrorMessage() : "未知错误";
            voiceTrainingService.completeFailed(taskUuid, errorMessage);
            return ResponseEntity.ok(ResponseResult.success(null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(ResponseResult.error("无效的任务ID格式"));
        } catch (Exception e) {
            log.error("训练失败回调异常: taskId={}", taskId, e);
            return ResponseEntity.internalServerError().body(ResponseResult.error("处理失败: " + e.getMessage()));
        }
    }

    @Operation(summary = "批量训练完成回调")
    @PostMapping("/complete/batch")
    public ResponseEntity<ResponseResult<BatchCallbackResponse>> completeBatch(
            @RequestBody BatchCallbackRequest request) {
        try {
            int successCount = 0;
            int failedCount = 0;

            for (BatchCallbackRequest.TaskResult result : request.getResults()) {
                try {
                    UUID taskUuid = UUID.fromString(result.getTaskId());
                    if ("success".equalsIgnoreCase(result.getStatus())) {
                        voiceTrainingService.completeSuccess(
                                taskUuid,
                                parseVoiceModelId(result.getVoiceModelId()),
                                result.getVoiceIdExternal(),
                                result.getSimilarityScore(),
                                result.getModelPath()
                        );
                        successCount++;
                    } else {
                        voiceTrainingService.completeFailed(taskUuid, result.getErrorMessage());
                        failedCount++;
                    }
                } catch (Exception e) {
                    log.error("批量回调处理单个任务失败: taskId={}", result.getTaskId(), e);
                    failedCount++;
                }
            }

            BatchCallbackResponse response = new BatchCallbackResponse();
            response.setSuccessCount(successCount);
            response.setFailedCount(failedCount);
            response.setTotal(request.getResults().size());
            return ResponseEntity.ok(ResponseResult.success(response));
        } catch (Exception e) {
            log.error("批量回调处理异常", e);
            return ResponseEntity.internalServerError().body(ResponseResult.error("批量处理失败: " + e.getMessage()));
        }
    }

    private UUID parseVoiceModelId(String rawVoiceModelId) {
        if (rawVoiceModelId == null || rawVoiceModelId.isBlank()) {
            return null;
        }
        try {
            return UUID.fromString(rawVoiceModelId);
        } catch (IllegalArgumentException e) {
            log.warn("AI callback voiceModelId is not UUID, fallback to server-generated id: {}", rawVoiceModelId);
            return null;
        }
    }

    @Data
    public static class ProgressCallbackRequest {
        @Parameter(description = "训练进度(0-100)")
        private BigDecimal progress;
    }

    @Data
    public static class SuccessCallbackRequest {
        @Parameter(description = "模型ID，可为空")
        private String voiceModelId;

        @Parameter(description = "外部voiceId")
        private String voiceIdExternal;

        @Parameter(description = "相似度评分")
        private BigDecimal similarityScore;

        @Parameter(description = "模型在OSS中的路径")
        private String modelPath;
    }

    @Data
    public static class FailedCallbackRequest {
        @Parameter(description = "错误信息")
        private String errorMessage;
    }

    @Data
    public static class BatchCallbackRequest {
        private List<TaskResult> results;

        @Data
        public static class TaskResult {
            private String taskId;
            private String status;
            private String voiceModelId;
            private String voiceIdExternal;
            private BigDecimal similarityScore;
            private String modelPath;
            private String errorMessage;
        }
    }

    @Data
    public static class BatchCallbackResponse {
        private int successCount;
        private int failedCount;
        private int total;
    }

    @Data
    public static class ResponseResult<T> {
        private Integer code;
        private String message;
        private T data;

        public static <T> ResponseResult<T> success(T data) {
            ResponseResult<T> response = new ResponseResult<>();
            response.setCode(200);
            response.setMessage("success");
            response.setData(data);
            return response;
        }

        public static <T> ResponseResult<T> error(String message) {
            ResponseResult<T> response = new ResponseResult<>();
            response.setCode(500);
            response.setMessage(message);
            return response;
        }
    }
}
