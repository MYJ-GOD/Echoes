package com.echoes.admin.domain.governance.controller;

import com.echoes.admin.domain.governance.service.VoiceGovernanceService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

/**
 * 音色与训练治理 Controller
 */
@Slf4j
@Tag(name = "音色与训练治理", description = "音色资产和训练任务管理")
@RestController
@RequestMapping("/admin/voice")
@RequiredArgsConstructor
public class VoiceController {

    private final VoiceGovernanceService voiceGovernanceService;

    /**
     * 查询音色资产列表
     */
    @GetMapping("/assets")
    @Operation(summary = "查询音色资产列表")
    public Map<String, Object> listVoiceAssets(
            @Parameter(description = "用户 ID") @RequestParam(value = "userId", required = false) String userId,
            @Parameter(description = "状态") @RequestParam(value = "status", required = false) String status,
            @Parameter(description = "角色") @RequestParam(value = "role", required = false) String role,
            @Parameter(description = "页码") @RequestParam(value = "page", defaultValue = "1") Integer page,
            @Parameter(description = "每页数量") @RequestParam(value = "size", defaultValue = "20") Integer size
    ) {
        return voiceGovernanceService.listVoiceAssets(userId, status, role, page, size);
    }

    /**
     * 获取音色资产详情
     */
    @GetMapping("/assets/{voiceAssetId}")
    @Operation(summary = "获取音色资产详情")
    public Map<String, Object> getVoiceAsset(
            @Parameter(description = "音色资产 ID", required = true) @PathVariable String voiceAssetId
    ) {
        return voiceGovernanceService.getVoiceAsset(voiceAssetId);
    }

    /**
     * 获取音色质量历史
     */
    @GetMapping("/assets/{voiceAssetId}/quality/history")
    @Operation(summary = "获取音色质量历史")
    public Map<String, Object> getQualityHistory(
            @Parameter(description = "音色资产 ID", required = true) @PathVariable String voiceAssetId
    ) {
        return voiceGovernanceService.getQualityHistory(voiceAssetId);
    }

    /**
     * 查询训练任务列表
     */
    @GetMapping("/training/tasks")
    @Operation(summary = "查询训练任务列表")
    public Map<String, Object> listTrainingTasks(
            @Parameter(description = "音色资产 ID") @RequestParam(value = "voiceAssetId", required = false) String voiceAssetId,
            @Parameter(description = "状态") @RequestParam(value = "status", required = false) String status,
            @Parameter(description = "页码") @RequestParam(value = "page", defaultValue = "1") Integer page,
            @Parameter(description = "每页数量") @RequestParam(value = "size", defaultValue = "20") Integer size
    ) {
        return voiceGovernanceService.listTrainingTasks(voiceAssetId, status, page, size);
    }

    /**
     * 获取训练任务详情
     */
    @GetMapping("/training/tasks/{taskId}")
    @Operation(summary = "获取训练任务详情")
    public Map<String, Object> getTrainingTask(
            @Parameter(description = "任务 ID", required = true) @PathVariable String taskId
    ) {
        return voiceGovernanceService.getTrainingTask(taskId);
    }

    /**
     * 获取训练任务日志链接
     */
    @GetMapping("/training/tasks/{taskId}/log-link")
    @Operation(summary = "获取训练任务日志链接")
    public Map<String, String> getTrainingTaskLogLink(
            @Parameter(description = "任务 ID", required = true) @PathVariable String taskId
    ) {
        return voiceGovernanceService.getTrainingTaskLogLink(taskId);
    }
}
