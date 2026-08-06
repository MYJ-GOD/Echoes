package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.common.result.Result;
import com.echoes.conversation.domain.chat.client.VoiceServiceWebClient;
import com.echoes.conversation.domain.chat.entity.dto.VoiceReferenceDTO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.util.Map;

@Tag(name = "Voice Reference", description = "Manage voice reference audios")
@RestController
@RequestMapping("/conversation/voice-ref")
@RequiredArgsConstructor
@Slf4j
public class VoiceReferenceController {

    private final VoiceServiceWebClient voiceServiceWebClient;
    private final ObjectMapper objectMapper;

    @PostMapping("/upload")
    public Mono<Result<VoiceReferenceDTO>> uploadReference(
            @RequestPart("audio_file") MultipartFile audioFile,
            @RequestParam(value = "ref_text", required = false) String refText,
            @RequestHeader(value = "X-USER-ID", required = false) String userId,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId
    ) {
        try {
            byte[] audioData = audioFile.getBytes();
            String filename = audioFile.getOriginalFilename();
            log.debug("上传语音参考音频，userId: {}, filename: {}", userId, filename);
            return voiceServiceWebClient.uploadVoiceReference(audioData, filename, refText, userId, traceId, sessionId, turnId)
                    .map(dto -> {
                        log.debug("Returning VoiceReferenceDTO: refId={}, refText={}", dto.getRefId(), dto.getRefText());
                        return Result.success(dto);
                    });
        } catch (IOException e) {
            log.error("Failed to read audio file", e);
            return Mono.just(Result.error("Failed to read audio file"));
        }
    }

    /**
     * 创建音色资产
     */
    @PostMapping("/assets")
    public Mono<Result<JsonNode>> createVoiceAsset(
            @RequestBody Map<String, Object> requestBody,
            @RequestHeader(value = "X-USER-ID", required = false) String userId
    ) {
        try {
            // 构建请求体
            String requestJson = objectMapper.writeValueAsString(requestBody);
            
            return voiceServiceWebClient.createVoiceAsset(requestJson, userId)
                    .map(response -> Result.success(response))
                    .onErrorResume(error -> {
                        log.error("创建音色资产失败: {}", error.getMessage());
                        return Mono.just(Result.error("创建音色资产失败: " + error.getMessage()));
                    });
        } catch (Exception e) {
            log.error("创建音色资产失败", e);
            return Mono.just(Result.error("创建音色资产失败: " + e.getMessage()));
        }
    }
}
