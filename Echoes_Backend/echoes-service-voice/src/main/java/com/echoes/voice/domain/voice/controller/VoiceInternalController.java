package com.echoes.voice.domain.voice.controller;

import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import com.echoes.voice.domain.voice.entity.po.VoiceModel;
import com.echoes.voice.domain.voice.entity.po.VoiceTrainingTask;
import com.echoes.voice.domain.voice.repository.VoiceAssetMapper;
import com.echoes.voice.domain.voice.repository.VoiceModelMapper;
import com.echoes.voice.domain.voice.repository.VoiceTrainingTaskMapper;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * Voice Internal API（内部服务调用）
 * 供 admin 等内部服务只读访问 voice 数据，不对外暴露（网关封堵 /internal/**）
 *
 * @author echoes
 */
@Slf4j
@RestController
@RequestMapping("/internal/voice")
@RequiredArgsConstructor
@Tag(name = "Voice Internal API", description = "内部服务调用接口（admin 等）")
public class VoiceInternalController {

    private final VoiceAssetMapper voiceAssetMapper;
    private final VoiceModelMapper voiceModelMapper;
    private final VoiceTrainingTaskMapper trainingTaskMapper;

    /**
     * 获取音色资产详情
     */
    @Operation(summary = "获取音色资产详情", description = "根据 voiceAssetId 获取音色资产（内部调用）")
    @GetMapping("/assets/{voiceAssetId}")
    public VoiceAsset getVoiceAsset(
            @PathVariable("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: getVoiceAsset voiceAssetId={}, X-INTERNAL={}", voiceAssetId, internal);
        return voiceAssetMapper.selectById(voiceAssetId);
    }

    /**
     * 获取音色资产列表（支持按 ownerUserId / status 过滤）
     */
    @Operation(summary = "获取音色资产列表", description = "按 ownerUserId / status 过滤，均为空则返回全部（内部调用）")
    @GetMapping("/assets")
    public List<VoiceAsset> listVoiceAssets(
            @RequestParam(value = "ownerUserId", required = false) UUID ownerUserId,
            @RequestParam(value = "status", required = false) String status,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: listVoiceAssets ownerUserId={}, status={}, X-INTERNAL={}", ownerUserId, status, internal);
        if (ownerUserId != null) {
            return voiceAssetMapper.selectByOwnerUserId(ownerUserId);
        }
        if (status != null && !status.isBlank()) {
            return voiceAssetMapper.selectByStatus(status);
        }
        return voiceAssetMapper.selectAll();
    }

    /**
     * 获取训练任务详情
     */
    @Operation(summary = "获取训练任务详情", description = "根据 taskId 获取训练任务（内部调用）")
    @GetMapping("/training/tasks/{taskId}")
    public VoiceTrainingTask getTrainingTask(
            @PathVariable("taskId") UUID taskId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: getTrainingTask taskId={}, X-INTERNAL={}", taskId, internal);
        return trainingTaskMapper.selectById(taskId);
    }

    /**
     * 获取训练任务列表（支持按 voiceAssetId / status 过滤）
     */
    @Operation(summary = "获取训练任务列表", description = "按 voiceAssetId / status 过滤，均为空则返回全部（内部调用）")
    @GetMapping("/training/tasks")
    public List<VoiceTrainingTask> listTrainingTasks(
            @RequestParam(value = "voiceAssetId", required = false) UUID voiceAssetId,
            @RequestParam(value = "status", required = false) String status,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: listTrainingTasks voiceAssetId={}, status={}, X-INTERNAL={}", voiceAssetId, status, internal);
        if (voiceAssetId != null) {
            return trainingTaskMapper.selectByVoiceAssetId(voiceAssetId);
        }
        if (status != null && !status.isBlank()) {
            return trainingTaskMapper.selectByStatus(status);
        }
        return trainingTaskMapper.selectAll();
    }

    /**
     * 获取音色最新成功模型
     */
    @Operation(summary = "获取音色最新模型", description = "根据 voiceAssetId 获取最新成功训练模型（内部调用）")
    @GetMapping("/models/latest/{voiceAssetId}")
    public VoiceModel getLatestModel(
            @PathVariable("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: getLatestModel voiceAssetId={}, X-INTERNAL={}", voiceAssetId, internal);
        return voiceModelMapper.selectLatestSuccessByAssetId(voiceAssetId);
    }

    /**
     * 获取音色所有模型（质量历史）
     */
    @Operation(summary = "获取音色所有模型", description = "根据 voiceAssetId 获取所有训练模型（质量历史，内部调用）")
    @GetMapping("/models")
    public List<VoiceModel> listModelsByAssetId(
            @RequestParam("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    ) {
        log.debug("InternalAPI: listModelsByAssetId voiceAssetId={}, X-INTERNAL={}", voiceAssetId, internal);
        return voiceModelMapper.selectByAssetId(voiceAssetId);
    }
}
