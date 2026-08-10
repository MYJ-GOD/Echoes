package com.echoes.admin.domain.governance.service;

import com.echoes.admin.domain.governance.client.VoiceServiceClient;
import com.echoes.admin.domain.governance.dto.VoiceAssetDTO;
import com.echoes.admin.domain.governance.dto.VoiceModelDTO;
import com.echoes.admin.domain.governance.dto.VoiceTrainingTaskDTO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.*;

/**
 * 音色治理服务（已重构：通过 VoiceServiceClient Feign 调用 voice internal API，不再直连 Mapper）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceGovernanceService {

    private final VoiceServiceClient voiceServiceClient;

    /**
     * 查询音色资产列表
     */
    public Map<String, Object> listVoiceAssets(String userId, String status, String role, int page, int size) {
        UUID ownerUserId = parseUuid(userId);
        List<VoiceAssetDTO> assets = voiceServiceClient.listVoiceAssets(ownerUserId, status, "1");

        // 过滤已删除
        assets = assets.stream()
                .filter(a -> a.getDeleted() == null || a.getDeleted() == 0)
                .toList();

        List<Map<String, Object>> voList = assets.stream()
                .map(this::convertToMap)
                .toList();

        Map<String, Object> response = new HashMap<>();
        response.put("list", voList);
        response.put("total", voList.size());
        response.put("page", page);
        response.put("size", size);
        return response;
    }

    /**
     * 获取音色资产详情
     */
    public Map<String, Object> getVoiceAsset(String voiceAssetId) {
        UUID id = parseUuid(voiceAssetId);
        if (id == null) {
            return Collections.emptyMap();
        }

        VoiceAssetDTO asset = voiceServiceClient.getVoiceAsset(id, "1");
        if (asset == null) {
            return Collections.emptyMap();
        }

        Map<String, Object> result = convertToMap(asset);

        // 获取最新模型
        VoiceModelDTO latestModel = voiceServiceClient.getLatestModel(id, "1");
        if (latestModel != null) {
            result.put("latestModel", convertModelToMap(latestModel));
        }

        return result;
    }

    /**
     * 获取音色质量历史
     */
    public Map<String, Object> getQualityHistory(String voiceAssetId) {
        UUID id = parseUuid(voiceAssetId);
        if (id == null) {
            return Collections.emptyMap();
        }

        VoiceAssetDTO asset = voiceServiceClient.getVoiceAsset(id, "1");
        if (asset == null) {
            return Collections.emptyMap();
        }

        // 获取所有模型（按时间排序）
        List<VoiceModelDTO> models = voiceServiceClient.listModelsByAssetId(id, "1");
        List<Map<String, Object>> qualityHistory = models.stream()
                .map(m -> {
                    Map<String, Object> entry = new HashMap<>();
                    entry.put("voiceModelId", m.getVoiceModelId() != null ? m.getVoiceModelId().toString() : null);
                    entry.put("modelVersion", m.getModelVersion());
                    entry.put("similarityScore", m.getSimilarityScore());
                    entry.put("status", m.getStatus());
                    entry.put("createTime", m.getCreateTime());
                    return entry;
                })
                .toList();

        Map<String, Object> result = new HashMap<>();
        result.put("voiceAssetId", voiceAssetId);
        result.put("currentQualityScore", asset.getQualityScore());
        result.put("history", qualityHistory);
        return result;
    }

    /**
     * 查询训练任务列表
     */
    public Map<String, Object> listTrainingTasks(String voiceAssetId, String status, int page, int size) {
        UUID assetId = parseUuid(voiceAssetId);
        List<VoiceTrainingTaskDTO> tasks = voiceServiceClient.listTrainingTasks(assetId, status, "1");

        List<Map<String, Object>> voList = tasks.stream()
                .map(this::convertTaskToMap)
                .toList();

        Map<String, Object> response = new HashMap<>();
        response.put("list", voList);
        response.put("total", voList.size());
        response.put("page", page);
        response.put("size", size);
        return response;
    }

    /**
     * 获取训练任务详情
     */
    public Map<String, Object> getTrainingTask(String taskId) {
        UUID id = parseUuid(taskId);
        if (id == null) {
            return Collections.emptyMap();
        }

        VoiceTrainingTaskDTO task = voiceServiceClient.getTrainingTask(id, "1");
        if (task == null) {
            return Collections.emptyMap();
        }

        return convertTaskToMap(task);
    }

    /**
     * 获取训练任务日志链接
     */
    public Map<String, String> getTrainingTaskLogLink(String taskId) {
        UUID id = parseUuid(taskId);
        if (id == null) {
            return Collections.emptyMap();
        }

        VoiceTrainingTaskDTO task = voiceServiceClient.getTrainingTask(id, "1");
        if (task == null || task.getLogPath() == null) {
            return Collections.emptyMap();
        }

        Map<String, String> result = new HashMap<>();
        result.put("taskId", taskId);
        result.put("logPath", task.getLogPath());
        result.put("logUrl", "/api/logs/view?path=" + task.getLogPath());
        return result;
    }

    private Map<String, Object> convertToMap(VoiceAssetDTO asset) {
        Map<String, Object> result = new HashMap<>();
        result.put("voiceAssetId", asset.getVoiceAssetId() != null ? asset.getVoiceAssetId().toString() : null);
        result.put("ownerUserId", asset.getOwnerUserId() != null ? asset.getOwnerUserId().toString() : null);
        result.put("name", asset.getName());
        result.put("role", asset.getRole());  // DTO 已是 String，无需 .getCode()
        result.put("status", asset.getStatus());  // DTO 已是 String，无需 .getCode()
        result.put("qualityScore", asset.getQualityScore());
        result.put("voiceIdExternal", asset.getVoiceIdExternal());
        result.put("createTime", asset.getCreateTime());
        result.put("updateTime", asset.getUpdateTime());
        return result;
    }

    private Map<String, Object> convertModelToMap(VoiceModelDTO model) {
        Map<String, Object> result = new HashMap<>();
        result.put("voiceModelId", model.getVoiceModelId() != null ? model.getVoiceModelId().toString() : null);
        result.put("modelVersion", model.getModelVersion());
        result.put("similarityScore", model.getSimilarityScore());
        result.put("status", model.getStatus());
        result.put("createTime", model.getCreateTime());
        return result;
    }

    private Map<String, Object> convertTaskToMap(VoiceTrainingTaskDTO task) {
        Map<String, Object> result = new HashMap<>();
        result.put("taskId", task.getTaskId() != null ? task.getTaskId().toString() : null);
        result.put("voiceAssetId", task.getVoiceAssetId() != null ? task.getVoiceAssetId().toString() : null);
        result.put("refId", task.getRefId());
        result.put("userId", task.getUserId() != null ? task.getUserId().toString() : null);
        result.put("status", task.getStatus());
        result.put("progress", task.getProgress());
        result.put("logPath", task.getLogPath());
        result.put("startTime", task.getStartTime());
        result.put("endTime", task.getEndTime());
        return result;
    }

    private UUID parseUuid(String uuidStr) {
        if (uuidStr == null || uuidStr.isBlank()) {
            return null;
        }
        try {
            return UUID.fromString(uuidStr);
        } catch (Exception e) {
            return null;
        }
    }
}
