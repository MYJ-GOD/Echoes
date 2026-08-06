package com.echoes.voice.domain.voice.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.echoes.context.BaseContext;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.voice.entity.dto.CreateTrainingTaskRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.query.TaskQueryRequest;
import com.echoes.voice.domain.voice.entity.dto.query.TaskListQueryRequest;
import com.echoes.voice.domain.voice.entity.dto.query.AssetTasksQueryRequest;
import com.echoes.voice.domain.voice.entity.dto.query.TaskOperationRequest;
import com.echoes.voice.domain.voice.entity.vo.TrainingTaskVO;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.service.IVoiceTrainingService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * 训练任务控制器
 * 提供训练任务的创建、查询、取消等接口
 */
@Tag(name = "训练任务管理", description = "训练任务的创建、查询、取消等接口")
@RestController
@RequestMapping("/voice/training")
@RequiredArgsConstructor
@Slf4j
public class VoiceTrainingController {

    private final IVoiceTrainingService voiceTrainingService;

    /**
     * 创建训练任务
     */
    @Operation(summary = "创建训练任务", description = "为音色资产创建训练任务，发起异步训练")
    @ApiResponses({
        @ApiResponse(responseCode = "201", description = "创建成功"),
        @ApiResponse(responseCode = "400", description = "请求参数错误"),
        @ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    @PostMapping
    public ResponseEntity<ResponseResult<TrainingTaskVO>> createTrainingTask(
            @Valid @RequestBody CreateTrainingTaskRequestDTO request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            TrainingTaskVO result = voiceTrainingService.createTrainingTask(request, userUuid);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(ResponseResult.success(result));
        } catch (VoiceServiceException e) {
            log.error("创建训练任务失败: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("创建训练任务异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("创建训练任务失败: " + e.getMessage()));
        }
    }

    /**
     * 查询任务详情
     */
    @Operation(summary = "查询任务详情", description = "获取训练任务的详细信息和进度")
    @GetMapping("/{taskId}")
    public ResponseEntity<ResponseResult<TrainingTaskVO>> getTask(@ModelAttribute TaskQueryRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            UUID taskUuid = UUID.fromString(request.getTaskId());
            TrainingTaskVO result = voiceTrainingService.getTask(taskUuid, userUuid);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的任务ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("查询任务详情异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("查询失败: " + e.getMessage()));
        }
    }

    /**
     * 查询用户任务列表
     */
    @Operation(summary = "查询用户任务列表", description = "分页查询当前用户的训练任务列表")
    @GetMapping
    public ResponseEntity<ResponseResult<Page<TrainingTaskVO>>> listUserTasks(@ModelAttribute TaskListQueryRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            Page<TrainingTaskVO> result = voiceTrainingService.listUserTasks(userUuid, request.getStatus(), request.getPageNum(), request.getPageSize());
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (Exception e) {
            log.error("查询任务列表异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("查询失败: " + e.getMessage()));
        }
    }

    /**
     * 查询音色资产的任务列表
     */
    @Operation(summary = "查询音色任务列表", description = "查询指定音色资产的所有训练任务")
    @GetMapping("/asset/{voiceAssetId}")
    public ResponseEntity<ResponseResult<List<TrainingTaskVO>>> listAssetTasks(@ModelAttribute AssetTasksQueryRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            UUID assetUuid = UUID.fromString(request.getVoiceAssetId());
            List<TrainingTaskVO> result = voiceTrainingService.listAssetTasks(assetUuid, userUuid);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的音色资产ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("查询音色任务列表异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("查询失败: " + e.getMessage()));
        }
    }

    /**
     * 取消训练任务
     */
    @Operation(summary = "取消训练任务", description = "取消正在进行或等待中的训练任务")
    @PostMapping("/{taskId}/cancel")
    public ResponseEntity<ResponseResult<Void>> cancelTask(@ModelAttribute TaskOperationRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            UUID taskUuid = UUID.fromString(request.getTaskId());
            voiceTrainingService.cancelTask(taskUuid, userUuid);
            return ResponseEntity.ok(ResponseResult.success(null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的任务ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("取消训练任务异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("取消失败: " + e.getMessage()));
        }
    }

    /**
     * 重试训练任务
     */
    @Operation(summary = "重试训练任务", description = "基于失败的任务重新创建训练任务")
    @PostMapping("/{taskId}/retry")
    public ResponseEntity<ResponseResult<TrainingTaskVO>> retryTask(
            @Parameter(description = "原任务ID") @PathVariable("taskId") String taskId,
            @RequestBody(required = false) CreateTrainingTaskRequestDTO request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            UUID taskUuid = UUID.fromString(taskId);
            TrainingTaskVO result = voiceTrainingService.retryTask(taskUuid, userUuid, request);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的任务ID格式"));
        } catch (VoiceServiceException e) {
            log.error("重试训练任务失败: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("重试训练任务异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("重试失败: " + e.getMessage()));
        }
    }

    /**
     * 获取用户ID
     */
    private UUID getUserId(String userId) {
        if (userId != null && !userId.isBlank()) {
            try {
                return UUID.fromString(userId);
            } catch (IllegalArgumentException e) {
                log.warn("无效的X-USER-ID格式: {}", userId);
            }
        }
        Object currentId = BaseContext.getCurrentId();
        if (currentId instanceof UUID) {
            return (UUID) currentId;
        }
        throw new VoiceServiceException(VoiceErrorEnum.USER_ID_REQUIRED, "用户ID不能为空");
    }

    /**
     * 获取训练测试音频
     */
    @Operation(summary = "获取测试音频", description = "获取训练生成的测试音频文件")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "获取成功"),
        @ApiResponse(responseCode = "404", description = "音频文件不存在"),
        @ApiResponse(responseCode = "403", description = "无权限访问")
    })
    @GetMapping("/model/{voiceModelId}/sample")
    public ResponseEntity<?> getTestAudio(
            @Parameter(description = "声纹模型ID") @PathVariable("voiceModelId") String voiceModelId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            UUID voiceModelUuid = UUID.fromString(voiceModelId);
            String audioPath = voiceTrainingService.getTestAudioPath(voiceModelUuid, userUuid);

            Resource resource = new FileSystemResource(audioPath);
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=test_audio.wav")
                    .contentType(MediaType.parseMediaType("audio/wav"))
                    .body(resource);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的模型ID格式"));
        } catch (VoiceServiceException e) {
            log.error("获取测试音频失败: {}", e.getMessage());
            if (e.getCode() == VoiceErrorEnum.VOICE_MODEL_NOT_FOUND.getCode() ||
                e.getCode() == VoiceErrorEnum.LOCAL_FILE_NOT_FOUND.getCode()) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(ResponseResult.error(e.getMessage()));
            }
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("获取测试音频异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("获取失败: " + e.getMessage()));
        }
    }

    /**
     * 统一API响应
     */
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

