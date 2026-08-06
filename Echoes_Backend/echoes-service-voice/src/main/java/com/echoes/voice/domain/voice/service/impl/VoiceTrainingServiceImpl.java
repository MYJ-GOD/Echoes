package com.echoes.voice.domain.voice.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.voice.entity.dto.CreateTrainingTaskRequestDTO;
import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import com.echoes.voice.domain.voice.entity.po.VoiceAuditLog;
import com.echoes.voice.domain.voice.entity.po.VoiceModel;
import com.echoes.voice.domain.voice.entity.po.VoiceTrainingTask;
import com.echoes.voice.domain.voice.entity.vo.TrainingTaskVO;
import com.echoes.voice.domain.voice.enums.AssetStatus;
import com.echoes.voice.domain.voice.enums.TaskStatus;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.mq.TrainingTaskProducer;
import com.echoes.voice.domain.voice.repository.VoiceAssetMapper;
import com.echoes.voice.domain.voice.repository.VoiceAuditLogMapper;
import com.echoes.voice.domain.voice.repository.VoiceModelMapper;
import com.echoes.voice.domain.voice.repository.VoiceRefMapper;
import com.echoes.voice.domain.voice.repository.VoiceTrainingTaskMapper;
import com.echoes.voice.domain.voice.service.IVoiceAssetService;
import com.echoes.voice.domain.voice.service.IVoiceTrainingService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceTrainingServiceImpl implements IVoiceTrainingService {

    private final VoiceTrainingTaskMapper trainingTaskMapper;
    private final VoiceAssetMapper voiceAssetMapper;
    private final VoiceModelMapper voiceModelMapper;
    private final VoiceAuditLogMapper voiceAuditLogMapper;
    private final VoiceRefMapper voiceRefMapper;
    private final IVoiceAssetService voiceAssetService;
    private final TrainingTaskProducer trainingTaskProducer;
    private final RedisTemplate<String, Object> redisTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final String TRAINING_CHANNEL_PREFIX = "voice:training:status:";

    @Override
    @Transactional(rollbackFor = Exception.class)
    public TrainingTaskVO createTrainingTask(CreateTrainingTaskRequestDTO request, UUID userId) {
        if (!voiceAssetService.isOwner(request.getVoiceAssetId(), userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Only owner can create training task");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(request.getVoiceAssetId());
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        VoiceTrainingTask existingTask = trainingTaskMapper.selectLatestByVoiceAssetId(request.getVoiceAssetId());
        if (existingTask != null && TaskStatus.TRAINING.name().equalsIgnoreCase(existingTask.getStatus())) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "A training task is already running");
        }

        String storageKey = request.getStorageKey();
        if (storageKey == null || storageKey.isBlank()) {
            storageKey = voiceRefMapper.selectStorageKeyById(request.getRefId());
            if (storageKey == null) {
                throw new VoiceServiceException(VoiceErrorEnum.VOICE_REF_NOT_FOUND, "Reference audio not found or expired");
            }
        }

        UUID newTaskId = UUID.randomUUID();
        VoiceTrainingTask task = VoiceTrainingTask.builder()
                .taskId(newTaskId)
                .voiceAssetId(request.getVoiceAssetId())
                .refId(request.getRefId())
                .userId(userId)
                .status(TaskStatus.PENDING.name())
                .progress(BigDecimal.ZERO)
                .logPath(buildTrainingLogPath(newTaskId))
                .startTime(LocalDateTime.now())
                .build();
        trainingTaskMapper.insert(task);

        // 发送训练任务到消息队列
        try {
            String recordId = trainingTaskProducer.sendStartTraining(
                    task.getTaskId(),
                    task.getVoiceAssetId(),
                    task.getRefId(),
                    storageKey,
                    userId,
                    request.getModelVersion(),
                    request.getPrompt()
            );
            log.info("训练任务已发送到消息队列：taskId={}, recordId={}", task.getTaskId(), recordId);
        } catch (Exception e) {
            log.error("发送训练任务到消息队列失败：taskId={}", task.getTaskId(), e);
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_TRAINING_FAILED, "发送训练任务失败：" + e.getMessage());
        }

        voiceAssetMapper.updateStatus(request.getVoiceAssetId(), AssetStatus.CREATING.getCode());

        writeAuditLog(
                request.getVoiceAssetId(),
                userId,
                "TRAINING_CREATE",
                "ALLOWED",
                String.format("Create training task: taskId=%s", task.getTaskId())
        );

        return convertToVO(task, asset.getName());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public TrainingTaskVO retryTask(UUID taskId, UUID userId, CreateTrainingTaskRequestDTO request) {
        VoiceTrainingTask originalTask = trainingTaskMapper.selectById(taskId);
        if (originalTask == null) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Training task not found");
        }
        if (!userId.equals(originalTask.getUserId())) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission to retry this task");
        }
        if (!TaskStatus.FAILED.name().equalsIgnoreCase(originalTask.getStatus())) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Retry is only allowed for failed tasks");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(originalTask.getVoiceAssetId());
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        CreateTrainingTaskRequestDTO retryRequest = request != null ? request : CreateTrainingTaskRequestDTO.builder()
                .voiceAssetId(originalTask.getVoiceAssetId())
                .refId(originalTask.getRefId())
                .modelVersion(originalTask.getModelVersion())
                .prompt(originalTask.getPrompt())
                .build();

        VoiceTrainingTask existingTask = trainingTaskMapper.selectLatestByVoiceAssetId(retryRequest.getVoiceAssetId());
        if (existingTask != null && TaskStatus.TRAINING.name().equalsIgnoreCase(existingTask.getStatus())) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "A training task is already running");
        }

        String storageKey = retryRequest.getStorageKey();
        if (storageKey == null || storageKey.isBlank()) {
            storageKey = voiceRefMapper.selectStorageKeyById(retryRequest.getRefId());
            if (storageKey == null) {
                throw new VoiceServiceException(VoiceErrorEnum.VOICE_REF_NOT_FOUND, "Reference audio not found or expired");
            }
        }

        UUID retryTaskId = UUID.randomUUID();
        VoiceTrainingTask newTask = VoiceTrainingTask.builder()
                .taskId(retryTaskId)
                .voiceAssetId(retryRequest.getVoiceAssetId())
                .refId(retryRequest.getRefId())
                .userId(userId)
                .status(TaskStatus.PENDING.name())
                .progress(BigDecimal.ZERO)
                .startTime(LocalDateTime.now())
                .retryCount(originalTask.getRetryCount() != null ? originalTask.getRetryCount() + 1 : 1)
                .modelVersion(retryRequest.getModelVersion())
                .prompt(retryRequest.getPrompt())
                .logPath(buildTrainingLogPath(retryTaskId))
                .build();
        trainingTaskMapper.insert(newTask);

        try {
            String recordId = trainingTaskProducer.sendStartTraining(
                    newTask.getTaskId(),
                    newTask.getVoiceAssetId(),
                    newTask.getRefId(),
                    storageKey,
                    userId,
                    retryRequest.getModelVersion(),
                    retryRequest.getPrompt()
            );
            log.info("Retry task sent to MQ: taskId={}, recordId={}", newTask.getTaskId(), recordId);
        } catch (Exception e) {
            log.error("Failed to send retry task to MQ: taskId={}", newTask.getTaskId(), e);
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_TRAINING_FAILED, "Failed to send retry task: " + e.getMessage());
        }

        voiceAssetMapper.updateStatus(retryRequest.getVoiceAssetId(), AssetStatus.CREATING.getCode());

        writeAuditLog(
                retryRequest.getVoiceAssetId(),
                userId,
                "TRAINING_RETRY",
                "ALLOWED",
                String.format("Retry training task: originalTaskId=%s, newTaskId=%s", taskId, newTask.getTaskId())
        );

        return convertToVO(newTask, asset.getName());
    }

    @Override
    public TrainingTaskVO getTask(UUID taskId, UUID userId) {
        VoiceTrainingTask task = trainingTaskMapper.selectById(taskId);
        if (task == null) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Task not found");
        }
        if (!task.getUserId().equals(userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission");
        }
        VoiceAsset asset = voiceAssetMapper.selectById(task.getVoiceAssetId());
        return convertToVO(task, asset != null ? asset.getName() : null);
    }

    @Override
    public Page<TrainingTaskVO> listUserTasks(UUID userId, String status, int pageNum, int pageSize) {
        int offset = (pageNum - 1) * pageSize;
        boolean hasStatus = status != null && !status.isBlank();

        // 数据库层分页查询
        long total = hasStatus
                ? trainingTaskMapper.countByUserIdAndStatus(userId, status)
                : trainingTaskMapper.countByUserId(userId);

        List<VoiceTrainingTask> tasks = hasStatus
                ? trainingTaskMapper.selectByUserIdAndStatusWithPage(userId, status, offset, pageSize)
                : trainingTaskMapper.selectByUserIdWithPage(userId, offset, pageSize);

        // 批量查询关联 VoiceAsset，避免 N+1
        List<UUID> assetIds = tasks.stream()
                .map(VoiceTrainingTask::getVoiceAssetId)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        Map<UUID, String> assetNameMap = assetIds.isEmpty()
                ? Map.of()
                : voiceAssetMapper.selectByIds(assetIds).stream()
                        .collect(Collectors.toMap(VoiceAsset::getVoiceAssetId, VoiceAsset::getName, (a, b) -> a));

        List<TrainingTaskVO> voList = tasks.stream()
                .map(task -> convertToVO(task, assetNameMap.get(task.getVoiceAssetId())))
                .collect(Collectors.toList());

        Page<TrainingTaskVO> resultPage = new Page<>(pageNum, pageSize);
        resultPage.setRecords(voList);
        resultPage.setTotal(total);
        return resultPage;
    }

    @Override
    public List<TrainingTaskVO> listAssetTasks(UUID voiceAssetId, UUID userId) {
        if (!voiceAssetService.hasAccessPermission(voiceAssetId, userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission");
        }

        List<VoiceTrainingTask> tasks = trainingTaskMapper.selectByVoiceAssetId(voiceAssetId);
        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        return tasks.stream()
                .map(task -> convertToVO(task, asset != null ? asset.getName() : null))
                .collect(Collectors.toList());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void cancelTask(UUID taskId, UUID userId) {
        VoiceTrainingTask task = trainingTaskMapper.selectById(taskId);
        if (task == null) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Task not found");
        }
        if (!task.getUserId().equals(userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission");
        }
        if (!TaskStatus.PENDING.name().equalsIgnoreCase(task.getStatus())
                && !TaskStatus.TRAINING.name().equalsIgnoreCase(task.getStatus())) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Task cannot be cancelled in current status");
        }

        trainingTaskProducer.sendCancelTraining(taskId, task.getVoiceAssetId(), userId);
        trainingTaskMapper.updateStatus(taskId, TaskStatus.CANCELLED.name());

        writeAuditLog(
                task.getVoiceAssetId(),
                userId,
                "TRAINING_CANCEL",
                "ALLOWED",
                String.format("Cancel training task: taskId=%s", taskId)
        );
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateProgress(UUID taskId, BigDecimal progress) {
        VoiceTrainingTask task = trainingTaskMapper.selectById(taskId);
        if (task == null) {
            log.warn("Update progress ignored, task not found: {}", taskId);
            return;
        }

        BigDecimal clamped = progress.min(BigDecimal.valueOf(100)).max(BigDecimal.ZERO);
        trainingTaskMapper.updateProgress(taskId, clamped);

        if (TaskStatus.PENDING.name().equalsIgnoreCase(task.getStatus())
                || TaskStatus.TRAINING.name().equalsIgnoreCase(task.getStatus())) {
            trainingTaskMapper.updateStatus(taskId, TaskStatus.TRAINING.name());
        }

        // 发布进度更新到 SSE 频道
        publishTrainingStatus(taskId.toString(), TaskStatus.TRAINING.name(), clamped.doubleValue(), task.getVoiceAssetId().toString(), null, null);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void completeSuccess(UUID taskId, UUID voiceModelId, String voiceIdExternal, BigDecimal similarityScore, String modelPath) {
        VoiceTrainingTask task = trainingTaskMapper.selectById(taskId);
        if (task == null) {
            log.warn("Complete success ignored, task not found: {}", taskId);
            return;
        }

        LocalDateTime now = LocalDateTime.now();
        UUID resolvedVoiceModelId = voiceModelId != null ? voiceModelId : UUID.randomUUID();
        Integer maxVersion = voiceModelMapper.selectMaxModelVersionByAssetId(task.getVoiceAssetId());
        int nextVersion = (maxVersion == null ? 0 : maxVersion) + 1;

        VoiceModel voiceModel = VoiceModel.builder()
                .voiceModelId(resolvedVoiceModelId)
                .voiceAssetId(task.getVoiceAssetId())
                .refId(task.getRefId())
                .modelVersion(nextVersion)
                .modelStorageKey(modelPath)
                .prompt(task.getPrompt())
                .status(TaskStatus.SUCCESS.name())
                .similarityScore(similarityScore)
                .build();
        voiceModelMapper.insert(voiceModel);

        trainingTaskMapper.updateComplete(taskId, TaskStatus.SUCCESS.name(), now, resolvedVoiceModelId);

        if (voiceIdExternal != null && !voiceIdExternal.isBlank()) {
            voiceAssetMapper.updateVoiceIdExternal(task.getVoiceAssetId(), voiceIdExternal);
        }
        voiceAssetMapper.updateQualityScore(task.getVoiceAssetId(), calculateQualityScore(similarityScore));
        voiceAssetMapper.updateStatus(task.getVoiceAssetId(), AssetStatus.READY.getCode());

        // 发布成功状态到 SSE 频道
        publishTrainingStatus(taskId.toString(), TaskStatus.SUCCESS.name(), 100.0, task.getVoiceAssetId().toString(), resolvedVoiceModelId.toString(), similarityScore != null ? similarityScore.doubleValue() : null);

        writeAuditLog(
                task.getVoiceAssetId(),
                task.getUserId(),
                "TRAINING_SUCCESS",
                "ALLOWED",
                String.format("Training success: taskId=%s, modelId=%s", taskId, resolvedVoiceModelId)
        );
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void completeFailed(UUID taskId, String errorMessage) {
        VoiceTrainingTask task = trainingTaskMapper.selectById(taskId);
        if (task == null) {
            log.warn("Complete failed ignored, task not found: {}", taskId);
            return;
        }

        LocalDateTime now = LocalDateTime.now();
        trainingTaskMapper.updateComplete(taskId, TaskStatus.FAILED.name(), now, null);
        voiceAssetMapper.updateStatus(task.getVoiceAssetId(), AssetStatus.FAILED.getCode());

        writeAuditLog(
                task.getVoiceAssetId(),
                task.getUserId(),
                "TRAINING_FAILED",
                "ALLOWED",
                String.format("Training failed: taskId=%s, error=%s", taskId, errorMessage)
        );

        // 发布失败状态到 SSE 频道
        publishTrainingStatus(taskId.toString(), TaskStatus.FAILED.name(), 0.0, task.getVoiceAssetId().toString(), null, null);
    }

    @Override
    public String getTestAudioPath(UUID voiceModelId, UUID userId) {
        VoiceModel voiceModel = voiceModelMapper.selectById(voiceModelId);
        if (voiceModel == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_MODEL_NOT_FOUND, "Voice model not found");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(voiceModel.getVoiceAssetId());
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        if (userId != null && asset.getOwnerUserId() != null && !asset.getOwnerUserId().equals(userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission to access this voice sample");
        }

        UUID ownerId = asset.getOwnerUserId();
        if (ownerId == null) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Asset owner not found");
        }

        String baseDir = System.getProperty("java.io.tmpdir") + java.io.File.separator + "echoes" + java.io.File.separator + "test_audio" + java.io.File.separator;
        String owner = ownerId.toString();
        String assetId = voiceModel.getVoiceAssetId().toString();

        String[] candidates = new String[]{
                baseDir + "test_user_" + owner + "_" + assetId + ".wav",
                baseDir + "test_user_" + owner.replace("-", "") + "_" + assetId.replace("-", "") + ".wav"
        };

        for (String candidate : candidates) {
            java.io.File audioFile = new java.io.File(candidate);
            if (audioFile.exists()) {
                return candidate;
            }
        }

        throw new VoiceServiceException(VoiceErrorEnum.LOCAL_FILE_NOT_FOUND, "Test audio file not found");
    }

    /**
     * 发布训练状态到 SSE 频道
     */
    private void publishTrainingStatus(String taskId, String status, Double progress, String voiceAssetId, String voiceModelId, Double similarityScore) {
        try {
            String channel = TRAINING_CHANNEL_PREFIX + taskId;
            String message = String.format("%s|%.1f|%s", status, progress != null ? progress : 0, status);
            redisTemplate.convertAndSend(channel, message);
            log.debug("发布训练状态：taskId={}, status={}, progress={}", taskId, status, progress);
        } catch (Exception e) {
            log.warn("发布训练状态失败：taskId={}, error={}", taskId, e.getMessage());
        }
    }

    private TrainingTaskVO convertToVO(VoiceTrainingTask task, String voiceAssetName) {
        // 查询 voice_model 获取相似度
        BigDecimal similarityScore = null;
        if (task.getVoiceModelId() != null) {
            VoiceModel voiceModel = voiceModelMapper.selectById(task.getVoiceModelId());
            if (voiceModel != null) {
                similarityScore = voiceModel.getSimilarityScore();
            }
        }

        return TrainingTaskVO.builder()
                .taskId(task.getTaskId())
                .voiceAssetId(task.getVoiceAssetId())
                .voiceAssetName(voiceAssetName)
                .voiceModelId(task.getVoiceModelId())
                .refId(task.getRefId())
                .status(task.getStatus())
                .statusDesc(getStatusDesc(task.getStatus()))
                .progress(task.getProgress())
                .progressText(task.getProgress() != null ? task.getProgress().setScale(1).toString() + "%" : "0%")
                .logPath(task.getLogPath())
                .estimatedTimeRemaining(estimateRemainingTime(task))
                .startTime(task.getStartTime())
                .endTime(task.getEndTime())
                .createTime(task.getCreateTime())
                .similarityScore(similarityScore)
                .build();
    }

    private String getStatusDesc(String status) {
        if (status == null) {
            return "Unknown";
        }
        return switch (status.toUpperCase()) {
            case "PENDING" -> "Pending";
            case "TRAINING" -> "Training";
            case "SUCCESS" -> "Success";
            case "FAILED" -> "Failed";
            case "CANCELLED" -> "Cancelled";
            default -> status;
        };
    }

    private String estimateRemainingTime(VoiceTrainingTask task) {
        if (!TaskStatus.TRAINING.name().equalsIgnoreCase(task.getStatus()) || task.getProgress() == null || task.getStartTime() == null) {
            return null;
        }

        BigDecimal progress = task.getProgress();
        if (progress.compareTo(BigDecimal.ZERO) <= 0) {
            return "Estimating...";
        }

        long elapsedMinutes = ChronoUnit.MINUTES.between(task.getStartTime(), LocalDateTime.now());
        double progressRate = progress.doubleValue() / 100.0;
        if (progressRate <= 0) {
            return null;
        }

        double totalEstimated = elapsedMinutes / progressRate;
        double remaining = totalEstimated - elapsedMinutes;
        if (remaining < 1) {
            return "Almost done";
        }
        if (remaining < 60) {
            return String.format("~%.0f min", remaining);
        }
        return String.format("~%.0f h", remaining / 60);
    }

    private void writeAuditLog(UUID voiceAssetId, UUID userId, String action, String result, String details) {
        try {
            VoiceAuditLog auditLog = VoiceAuditLog.builder()
                    .auditId(UUID.randomUUID())
                    .voiceAssetId(voiceAssetId)
                    .actorUserId(userId)
                    .action(action)
                    .result(result)
                    .details(buildAuditDetails(action, result, details))
                    .ts(LocalDateTime.now())
                    .build();
            voiceAuditLogMapper.insert(auditLog);
        } catch (Exception e) {
            log.error("Write audit log failed: voiceAssetId={}, action={}", voiceAssetId, action, e);
        }
    }

    private BigDecimal calculateQualityScore(BigDecimal similarityScore) {
        if (similarityScore == null) {
            return null;
        }
        BigDecimal bounded = similarityScore.max(BigDecimal.ZERO).min(BigDecimal.ONE);
        return bounded.setScale(2, java.math.RoundingMode.HALF_UP);
    }

    private String buildAuditDetails(String action, String result, String summary) {
        Map<String, Object> details = new LinkedHashMap<>();
        details.put("summary", summary);
        details.put("action", action);
        details.put("result", result);
        details.put("source", "echoes-service-voice");
        details.put("updatedAt", LocalDateTime.now().toString());
        try {
            return objectMapper.writeValueAsString(details);
        } catch (Exception e) {
            return String.format("{\"summary\":\"%s\",\"action\":\"%s\",\"result\":\"%s\"}",
                    summary == null ? "" : summary.replace("\"", "'"),
                    action == null ? "" : action,
                    result == null ? "" : result);
        }
    }

    private String buildTrainingLogPath(UUID taskId) {
        return String.format("logs/voice-training/%s.log", taskId);
    }

}
