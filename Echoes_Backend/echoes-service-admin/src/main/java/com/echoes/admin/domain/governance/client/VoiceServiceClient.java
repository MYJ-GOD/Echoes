package com.echoes.admin.domain.governance.client;

import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import com.echoes.voice.domain.voice.entity.po.VoiceTrainingTask;
import com.echoes.voice.domain.voice.entity.po.VoiceModel;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;

import java.util.List;
import java.util.UUID;

/**
 * Voice Service Feign 客户端
 * 用于 admin 模块只读访问 voice 服务数据
 */
@FeignClient(
        name = "echoes-service-voice",
        path = "/internal/voice",
        contextId = "voiceAssetClient",
        configuration = com.echoes.admin.config.FeignConfig.class
)
public interface VoiceServiceClient {

    /**
     * 获取音色资产详情
     */
    @GetMapping("/internal/voice/assets/{voiceAssetId}")
    VoiceAsset getVoiceAsset(
            @PathVariable("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 获取音色资产列表
     */
    @GetMapping("/internal/voice/assets")
    List<VoiceAsset> listVoiceAssets(
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 获取训练任务详情
     */
    @GetMapping("/internal/voice/training/tasks/{taskId}")
    VoiceTrainingTask getTrainingTask(
            @PathVariable("taskId") UUID taskId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );

    /**
     * 获取音色最新模型
     */
    @GetMapping("/internal/voice/models/latest/{voiceAssetId}")
    VoiceModel getLatestModel(
            @PathVariable("voiceAssetId") UUID voiceAssetId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internal
    );
}
