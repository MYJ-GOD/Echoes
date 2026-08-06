package com.echoes.voice.domain.voice.controller;

import com.echoes.context.BaseContext;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.service.IVoiceTrainingService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 训练状态 SSE 控制器
 * 通过 SSE 实时推送训练进度和状态变化
 */
@Tag(name = "训练状态推送", description = "SSE 实时推送训练进度和状态")
@RestController
@RequestMapping("/voice/training")
@RequiredArgsConstructor
@Slf4j
public class TrainingStatusSseController {

    private final RedisTemplate<String, Object> redisTemplate;
    private final IVoiceTrainingService voiceTrainingService;
    private final RedisMessageListenerContainer redisMessageListenerContainer;

    /**
     * SSE 连接存储
     * key: taskId
     * value: SseEmitter
     */
    private static final Map<String, SseEmitter> EMITTER_MAP = new ConcurrentHashMap<>();

    /**
     * Redis 频道前缀
     */
    private static final String TRAINING_CHANNEL_PREFIX = "voice:training:status:";

    /**
     * 订阅训练状态 SSE 事件流
     *
     * @param taskId 任务ID
     * @return SSE 事件流
     */
    @Operation(summary = "订阅训练状态", description = "通过 SSE 实时获取训练进度和状态变化")
    @ApiResponses({
        @ApiResponse(responseCode = "200", description = "SSE 连接建立成功"),
        @ApiResponse(responseCode = "400", description = "无效的任务ID"),
        @ApiResponse(responseCode = "403", description = "无权限访问")
    })
    @GetMapping(value = "/stream/{taskId}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribeTrainingStatus(
            @Parameter(description = "训练任务ID") @PathVariable("taskId") String taskId,
            @RequestParam(value = "token", required = false) String token,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {

        // 验证权限（优先使用 header 中的 userId）
        UUID userUuid = getUserId(userId);

        // 创建 SSE Emitter，超时时间 30 分钟（训练最长可能耗时）
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);

        String channel = TRAINING_CHANNEL_PREFIX + taskId;

        try {
            // 立即发送连接成功消息
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data(Map.of("taskId", taskId, "message", "SSE 连接已建立")));

            // 如果任务已完成或失败，立即发送当前状态
            try {
                var task = voiceTrainingService.getTask(UUID.fromString(taskId), userUuid);
                if (task != null) {
                    String status = task.getStatus();
                    if ("success".equalsIgnoreCase(status) || "failed".equalsIgnoreCase(status) || "cancelled".equalsIgnoreCase(status)) {
                        emitter.send(SseEmitter.event()
                                .name("status_change")
                                .data(Map.of(
                                        "taskId", taskId,
                                        "status", status,
                                        "progress", task.getProgress() != null ? task.getProgress().doubleValue() * 100 : 0,
                                        "voiceAssetId", task.getVoiceAssetId() != null ? task.getVoiceAssetId().toString() : "",
                                        "voiceModelId", task.getVoiceModelId() != null ? task.getVoiceModelId().toString() : "",
                                        "similarityScore", task.getSimilarityScore() != null ? task.getSimilarityScore() : 0
                                )));
                    }
                }
            } catch (Exception e) {
                log.warn("获取任务状态失败: {}", e.getMessage());
            }

            // 注册 Redis 订阅
            MessageListener listener = (Message message, byte[] pattern) -> {
                try {
                    String data = new String(message.getBody());
                    log.debug("收到训练状态消息: {}", data);

                    // 解析消息并转发给客户端
                    if (data.startsWith("{")) {
                        emitter.send(SseEmitter.event()
                                .name("progress")
                                .data(data));
                    } else {
                        // 简单消息格式: status|progress|message
                        String[] parts = data.split("\\|");
                        if (parts.length >= 2) {
                            emitter.send(SseEmitter.event()
                                    .name("progress")
                                    .data(Map.of(
                                            "taskId", taskId,
                                            "status", parts[0],
                                            "progress", Double.parseDouble(parts[1]),
                                            "message", parts.length > 2 ? parts[2] : ""
                                    )));
                        }
                    }
                } catch (IOException e) {
                    log.error("发送 SSE 消息失败: {}", e.getMessage());
                }
            };

            redisMessageListenerContainer.addMessageListener(listener, new ChannelTopic(channel));
            EMITTER_MAP.put(taskId, emitter);

            // 处理完成/超时/错误
            emitter.onCompletion(() -> {
                log.info("SSE 连接完成: taskId={}", taskId);
                EMITTER_MAP.remove(taskId);
                redisMessageListenerContainer.removeMessageListener(listener);
            });

            emitter.onTimeout(() -> {
                log.info("SSE 连接超时: taskId={}", taskId);
                EMITTER_MAP.remove(taskId);
                redisMessageListenerContainer.removeMessageListener(listener);
            });

            emitter.onError(e -> {
                log.error("SSE 连接错误: taskId={}, error={}", taskId, e.getMessage());
                EMITTER_MAP.remove(taskId);
                redisMessageListenerContainer.removeMessageListener(listener);
            });

        } catch (IOException e) {
            log.error("初始化 SSE 失败: taskId={}, error={}", taskId, e.getMessage());
            emitter.completeWithError(e);
        }

        return emitter;
    }

    /**
     * 手动触发状态推送（供内部调用）
     */
    @Operation(summary = "推送训练状态", description = "内部接口，用于推送训练进度和状态变化")
    @PostMapping("/push/{taskId}")
    public ResponseEntity<?> pushTrainingStatus(
            @Parameter(description = "训练任务ID") @PathVariable("taskId") String taskId,
            @RequestBody Map<String, Object> statusData) {

        SseEmitter emitter = EMITTER_MAP.get(taskId);
        if (emitter != null) {
            try {
                emitter.send(SseEmitter.event()
                        .name("status_change")
                        .data(statusData));
                return ResponseEntity.ok(Map.of("success", true));
            } catch (IOException e) {
                log.error("推送状态失败: {}", e.getMessage());
                return ResponseEntity.internalServerError().body(Map.of("success", false, "error", e.getMessage()));
            }
        }
        return ResponseEntity.ok(Map.of("success", true, "message", "无活跃连接"));
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
}

