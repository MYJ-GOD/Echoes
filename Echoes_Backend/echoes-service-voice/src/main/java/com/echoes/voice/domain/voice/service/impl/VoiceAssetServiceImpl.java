package com.echoes.voice.domain.voice.service.impl;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.inference.client.EchoesAiClient;
import com.echoes.voice.domain.voice.entity.dto.CreateVoiceAssetRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.UpdateVoiceAssetRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.VoiceAssetQueryDTO;
import com.echoes.voice.domain.voice.entity.po.UserVoiceLink;
import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import com.echoes.voice.domain.voice.entity.po.VoiceAuditLog;
import com.echoes.voice.domain.voice.entity.po.VoiceGrant;
import com.echoes.voice.domain.voice.entity.po.VoiceModel;
import com.echoes.voice.domain.voice.entity.po.VoiceRef;
import com.echoes.voice.domain.voice.entity.po.VoiceTrainingTask;
import com.echoes.voice.domain.voice.entity.vo.VoiceAssetVO;
import com.echoes.voice.domain.voice.enums.AssetStatus;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.enums.VoiceRole;
import com.echoes.voice.domain.voice.mq.TrainingTaskProducer;
import com.echoes.voice.domain.voice.repository.UserVoiceLinkMapper;
import com.echoes.voice.domain.voice.repository.VoiceAssetMapper;
import com.echoes.voice.domain.voice.repository.VoiceAuditLogMapper;
import com.echoes.voice.domain.voice.repository.VoiceGrantMapper;
import com.echoes.voice.domain.voice.repository.VoiceModelMapper;
import com.echoes.voice.domain.voice.repository.VoiceRefMapper;
import com.echoes.voice.domain.voice.repository.VoiceTrainingTaskMapper;
import com.echoes.voice.domain.voice.service.IVoiceAssetService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceAssetServiceImpl implements IVoiceAssetService {

    private final VoiceAssetMapper voiceAssetMapper;
    private final VoiceGrantMapper voiceGrantMapper;
    private final VoiceAuditLogMapper voiceAuditLogMapper;
    private final UserVoiceLinkMapper userVoiceLinkMapper;
    private final VoiceRefMapper voiceRefMapper;
    private final VoiceModelMapper voiceModelMapper;
    private final VoiceTrainingTaskMapper trainingTaskMapper;
    private final TrainingTaskProducer trainingTaskProducer;
    private final EchoesAiClient echoesAiClient;
    private final ObjectMapper objectMapper;

    private static final int MAX_VOICE_ASSETS_PER_USER = 10;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public VoiceAssetVO createVoiceAsset(CreateVoiceAssetRequestDTO request, UUID userId) {
        int count = voiceAssetMapper.countByUserId(userId);
        if (count >= MAX_VOICE_ASSETS_PER_USER) {
            throw new VoiceServiceException(
                    VoiceErrorEnum.MAX_VOICE_LIMIT_EXCEEDED,
                    "User voice asset limit exceeded, max: " + MAX_VOICE_ASSETS_PER_USER
            );
        }

        VoiceRef voiceRef = ensureVoiceRef(request.getRefId(), userId);
        if (voiceRef == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_REF_NOT_FOUND, "参考音频不存在或已过期");
        }
        if (!userId.equals(voiceRef.getOwnerUserId())) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "参考音频不属于当前用户");
        }

        VoiceAsset voiceAsset = VoiceAsset.builder()
                .voiceAssetId(UUID.randomUUID())
                .ownerUserId(userId)
                .name(request.getName())
                .role(VoiceRole.fromCode(request.getRole()))
                .tags(convertTagsToJson(request.getTags()))
                .status(AssetStatus.CREATING)
                .build();
        voiceAssetMapper.insert(voiceAsset);

        UUID taskId = UUID.randomUUID();
        VoiceTrainingTask task = VoiceTrainingTask.builder()
                .taskId(taskId)
                .voiceAssetId(voiceAsset.getVoiceAssetId())
                .refId(request.getRefId())
                .userId(userId)
                .status("pending")
                .progress(BigDecimal.ZERO)
                .modelVersion(1)
                .logPath(buildTrainingLogPath(taskId))
                .startTime(LocalDateTime.now())
                .build();
        trainingTaskMapper.insert(task);

        trainingTaskProducer.sendStartTraining(
                task.getTaskId(),
                task.getVoiceAssetId(),
                task.getRefId(),
                voiceRef.getStorageKey(),
                userId,
                1,
                null
        );

        if (Boolean.TRUE.equals(request.getSetAsDefault())) {
            setDefaultVoice(voiceAsset.getVoiceAssetId(), userId);
        }

        writeAuditLog(voiceAsset.getVoiceAssetId(), userId, "CREATE", "ALLOWED", null);
        writeAuditLog(
                voiceAsset.getVoiceAssetId(),
                userId,
                "TRAINING_CREATE",
                "ALLOWED",
                String.format("Create training task: taskId=%s", task.getTaskId())
        );

        log.info("Created voice asset and submitted training: voiceAssetId={}, taskId={}", voiceAsset.getVoiceAssetId(), task.getTaskId());
        return convertToVO(voiceAsset, false);
    }

    @Override
    public Page<VoiceAssetVO> listUserVoices(UUID userId, VoiceAssetQueryDTO query) {
        int pageNum = query.getPageNum() != null ? query.getPageNum() : 1;
        int pageSize = query.getPageSize() != null ? query.getPageSize() : 20;

        List<VoiceAsset> assets;
        if (StringUtils.hasText(query.getStatus())) {
            assets = voiceAssetMapper.selectByUserIdAndStatus(userId, query.getStatus());
        } else if (StringUtils.hasText(query.getRole())) {
            assets = voiceAssetMapper.selectByUserIdAndRole(userId, query.getRole());
        } else {
            assets = voiceAssetMapper.selectByOwnerUserId(userId);
        }

        List<VoiceAssetVO> voList = assets.stream()
                .map(asset -> convertToVO(asset, false))
                .collect(Collectors.toList());

        Page<VoiceAssetVO> resultPage = new Page<>(pageNum, pageSize);
        resultPage.setRecords(voList);
        resultPage.setTotal(voList.size());
        return resultPage;
    }

    @Override
    public VoiceAssetVO getVoiceAsset(UUID voiceAssetId, UUID userId) {
        if (!hasAccessPermission(voiceAssetId, userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission to access this voice asset");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        return convertToVO(asset, false);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public VoiceAssetVO updateVoiceAsset(UUID voiceAssetId, UpdateVoiceAssetRequestDTO request, UUID userId) {
        if (!isOwner(voiceAssetId, userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Only owner can update voice asset");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        if (StringUtils.hasText(request.getName())) {
            asset.setName(request.getName());
        }
        if (request.getRole() != null) {
            asset.setRole(VoiceRole.fromCode(request.getRole()));
        }
        if (request.getTags() != null) {
            asset.setTags(convertTagsToJson(request.getTags()));
        }

        voiceAssetMapper.update(asset);
        writeAuditLog(voiceAssetId, userId, "UPDATE", "ALLOWED", null);
        return convertToVO(asset, false);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteVoiceAsset(UUID voiceAssetId, UUID userId) {
        if (!isOwner(voiceAssetId, userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Only owner can delete voice asset");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        voiceAssetMapper.softDelete(voiceAssetId, LocalDateTime.now());
        voiceGrantMapper.deleteByVoiceAssetId(voiceAssetId);
        userVoiceLinkMapper.deleteByVoiceAssetId(voiceAssetId);

        writeAuditLog(voiceAssetId, userId, "DELETE", "ALLOWED", null);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void setDefaultVoice(UUID voiceAssetId, UUID userId) {
        if (!hasAccessPermission(voiceAssetId, userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "No permission to access this voice asset");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset not found");
        }

        if (!AssetStatus.READY.equals(asset.getStatus())) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Only ready voice can be set as default");
        }

        UserVoiceLink existingLink = userVoiceLinkMapper.selectByUserIdAndAssetId(userId, voiceAssetId);
        if (existingLink != null) {
            userVoiceLinkMapper.clearDefaultByUserId(userId);
            userVoiceLinkMapper.setDefault(existingLink.getLinkId());
        } else {
            UserVoiceLink newLink = UserVoiceLink.builder()
                    .linkId(UUID.randomUUID())
                    .userId(userId)
                    .voiceAssetId(voiceAssetId)
                    .isDefault(1)
                    .isDeleted(0)
                    .build();
            userVoiceLinkMapper.insert(newLink);
        }

        writeAuditLog(voiceAssetId, userId, "SET_DEFAULT", "ALLOWED", "Set as default voice");
    }

    @Override
    public boolean hasAccessPermission(UUID voiceAssetId, UUID userId) {
        if (isOwner(voiceAssetId, userId)) {
            return true;
        }
        List<VoiceGrant> grants = voiceGrantMapper.selectValidGrantsByUserId(userId, LocalDateTime.now());
        return grants.stream().anyMatch(grant -> grant.getVoiceAssetId().equals(voiceAssetId));
    }

    @Override
    public boolean isOwner(UUID voiceAssetId, UUID userId) {
        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        return asset != null && asset.getOwnerUserId().equals(userId);
    }

    @Override
    public List<VoiceAssetVO> getAvailableVoices(UUID userId) {
        List<VoiceAssetVO> result = new java.util.ArrayList<>();

        // 1. 获取用户自己的音色
        List<VoiceAsset> ownAssets = voiceAssetMapper.selectByOwnerUserId(userId);
        for (VoiceAsset asset : ownAssets) {
            if (asset.getDeleted() == null || asset.getDeleted() == 0) {
                result.add(convertToVO(asset, false));
            }
        }

        // 2. 获取收到的分享
        List<VoiceGrant> grants = voiceGrantMapper.selectValidGrantsByUserId(userId, LocalDateTime.now());
        for (VoiceGrant grant : grants) {
            VoiceAsset sharedAsset = voiceAssetMapper.selectById(grant.getVoiceAssetId());
            if (sharedAsset != null && (sharedAsset.getDeleted() == null || sharedAsset.getDeleted() == 0)) {
                VoiceAssetVO vo = convertToVO(sharedAsset, false);
                result.add(vo);
            }
        }

        return result;
    }

    private VoiceAssetVO convertToVO(VoiceAsset asset, boolean isDefault) {
        // 获取最新成功的模型信息
        VoiceModel latestModel = voiceModelMapper.selectLatestSuccessByAssetId(asset.getVoiceAssetId());

        return VoiceAssetVO.builder()
                .voiceAssetId(asset.getVoiceAssetId())
                .ownerUserId(asset.getOwnerUserId())
                .name(asset.getName())
                .role(asset.getRole() != null ? asset.getRole().getCode() : null)
                .roleDesc(asset.getRole() != null ? asset.getRole().getDesc() : null)
                .tags(convertJsonToTags(asset.getTags()))
                .status(asset.getStatus() != null ? asset.getStatus().getCode() : null)
                .statusDesc(asset.getStatus() != null ? asset.getStatus().getDesc() : null)
                .voiceIdExternal(asset.getVoiceIdExternal())
                .qualityScore(asset.getQualityScore())
                .isDefault(isDefault)
                .createTime(asset.getCreateTime())
                .updateTime(asset.getUpdateTime())
                .similarityScore(latestModel != null ? latestModel.getSimilarityScore() : null)
                .voiceModelId(latestModel != null ? latestModel.getVoiceModelId() : null)
                .build();
    }

    private String convertTagsToJson(List<String> tags) {
        if (tags == null || tags.isEmpty()) {
            return null;
        }
        try {
            return objectMapper.writeValueAsString(tags);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize tags", e);
            return null;
        }
    }

    private List<String> convertJsonToTags(String json) {
        if (!StringUtils.hasText(json)) {
            return null;
        }
        try {
            return objectMapper.readValue(
                    json,
                    objectMapper.getTypeFactory().constructCollectionType(List.class, String.class)
            );
        } catch (JsonProcessingException e) {
            log.error("Failed to parse tags json: {}", json, e);
            return null;
        }
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
            log.error("Failed to write audit log: voiceAssetId={}, action={}", voiceAssetId, action, e);
        }
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
        } catch (JsonProcessingException e) {
            return String.format("{\"summary\":\"%s\",\"action\":\"%s\",\"result\":\"%s\"}",
                    summary == null ? "" : summary.replace("\"", "'"),
                    action == null ? "" : action,
                    result == null ? "" : result);
        }
    }

    private VoiceRef ensureVoiceRef(String refId, UUID userId) {
        VoiceRef existing = voiceRefMapper.selectById(refId);
        if (existing != null) {
            return existing;
        }

        try {
            JsonNode ref = echoesAiClient.getVoiceReference(refId, null, null, null);
            if (ref == null || !ref.path("exists").asBoolean(false)) {
                return null;
            }

            String storageKey = ref.path("audio_path").asText(null);
            if (!StringUtils.hasText(storageKey)) {
                return null;
            }

            // Get duration_ms from response (may be null if not available)
            Integer durationMs = null;
            if (ref.has("duration_ms") && !ref.path("duration_ms").isNull()) {
                durationMs = ref.path("duration_ms").asInt();
            }

            VoiceRef newRef = VoiceRef.builder()
                    .refId(refId)
                    .ownerUserId(userId)
                    .conversationId(null)
                    .storageKey(storageKey)
                    .format(extractFormat(storageKey))
                    .durationMs(durationMs)
                    .expiresAt(LocalDateTime.now().plusDays(7))
                    .build();
            voiceRefMapper.insert(newRef);
            return newRef;
        } catch (Exception e) {
            log.warn("Failed to ensure voice_ref for refId={}: {}", refId, e.getMessage());
            return null;
        }
    }

    private String extractFormat(String storageKey) {
        try {
            Path path = Paths.get(storageKey);
            String fileName = path.getFileName() != null ? path.getFileName().toString() : "";
            int dot = fileName.lastIndexOf('.');
            if (dot >= 0 && dot < fileName.length() - 1) {
                return fileName.substring(dot + 1).toLowerCase();
            }
        } catch (Exception e) {
            log.debug("Failed to extract format from storageKey: {}", storageKey, e);
        }
        return "wav";
    }

    private String buildTrainingLogPath(UUID taskId) {
        return String.format("logs/voice-training/%s.log", taskId);
    }
}
