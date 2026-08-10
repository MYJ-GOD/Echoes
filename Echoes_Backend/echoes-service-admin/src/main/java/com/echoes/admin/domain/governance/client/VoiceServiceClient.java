package com.echoes.admin.domain.governance.client;

import com.echoes.admin.domain.governance.dto.VoiceAssetDTO;
import com.echoes.admin.domain.governance.dto.VoiceModelDTO;
import com.echoes.admin.domain.governance.dto.VoiceTrainingTaskDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.UUID;

/**
 * Voice Service Feign 客户端（使用 admin 本地 DTO，解耦 voice jar 依赖）
 */
@FeignClient(
        name = "echoes-service-voice",
        path = "/internal/voice",
        contextId = "voiceAssetClient",
        configuration = com.echoes.admin.config.FeignConfig.class
)
public interface VoiceServiceClient {

    @GetMapping("/assets/{voiceAssetId}")
    VoiceAssetDTO getVoiceAsset(
            @PathVariable("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/assets")
    List<VoiceAssetDTO> listVoiceAssets(
            @RequestParam(value = "ownerUserId", required = false) UUID ownerUserId,
            @RequestParam(value = "status", required = false) String status,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/training/tasks/{taskId}")
    VoiceTrainingTaskDTO getTrainingTask(
            @PathVariable("taskId") UUID taskId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/training/tasks")
    List<VoiceTrainingTaskDTO> listTrainingTasks(
            @RequestParam(value = "voiceAssetId", required = false) UUID voiceAssetId,
            @RequestParam(value = "status", required = false) String status,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/models/latest/{voiceAssetId}")
    VoiceModelDTO getLatestModel(
            @PathVariable("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    @GetMapping("/models")
    List<VoiceModelDTO> listModelsByAssetId(
            @RequestParam("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );
}
