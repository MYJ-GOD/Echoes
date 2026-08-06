package com.echoes.voice.domain.inference.controller;

import com.echoes.context.BaseContext;
import com.echoes.utils.UuidUtils;
import com.echoes.voice.common.constants.JwtClaimsConstant;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.config.JwtProperties;
import com.echoes.voice.domain.inference.entity.dto.SynthesizeRefRequestDTO;
import com.echoes.voice.domain.inference.entity.dto.SynthesizeRequestDTO;
import com.echoes.voice.domain.inference.entity.vo.SynthesizeResponseVO;
import com.echoes.voice.domain.inference.service.IVoiceCloneService;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.service.impl.VoiceQualityScoreService;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.io.IOUtils;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;

import java.io.File;
import java.nio.charset.StandardCharsets;

@RestController
@RequestMapping("/internal/voice/inference")
@RequiredArgsConstructor
@Slf4j
public class VoiceInferenceController {

    private final IVoiceCloneService voiceCloneService;
    private final VoiceQualityScoreService voiceQualityScoreService;
    private final JwtProperties jwtProperties;

    @PostMapping(value = "/synthesize-text", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> synthesizeText(
            @Valid @RequestBody SynthesizeRequestDTO request,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        try {
            bindUserContext(userId, authorization);

            SynthesizeResponseVO responseVO = voiceCloneService.synthesizeText(request, traceId, sessionId, turnId);
            if (responseVO.getSuccess() == null || !responseVO.getSuccess()) {
                voiceQualityScoreService.adjustByInferenceResult(request.getVoiceName(), false, "sync_synthesize_text_error");
                return ResponseEntity.internalServerError().build();
            }

            byte[] audioData = java.util.Base64.getDecoder().decode(responseVO.getAudioData());
            voiceQualityScoreService.adjustByInferenceResult(request.getVoiceName(), true, "sync_synthesize_text");

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.parseMediaType("audio/wav"));
            String encodedFilename = java.net.URLEncoder.encode(responseVO.getVoiceName() + "_output.wav", StandardCharsets.UTF_8)
                    .replace("+", "%20");
            headers.setContentDisposition(
                    ContentDisposition.inline()
                            .filename(encodedFilename, StandardCharsets.UTF_8)
                            .build()
            );
            return ResponseEntity.ok().headers(headers).body(audioData);
        } catch (Exception e) {
            log.error("synthesizeText failed", e);
            voiceQualityScoreService.adjustByInferenceResult(request.getVoiceName(), false, "sync_synthesize_text_exception");
            return ResponseEntity.internalServerError().build();
        } finally {
            BaseContext.removeCurrentId();
        }
    }

    @PostMapping(value = "/synthesize-text-ref", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> synthesizeTextWithRefId(
            @Valid @RequestBody SynthesizeRefRequestDTO request,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        try {
            bindUserContext(userId, authorization);

            SynthesizeResponseVO responseVO = voiceCloneService.synthesizeTextWithRefId(request, traceId, sessionId, turnId);
            if (responseVO.getSuccess() == null || !responseVO.getSuccess()) {
                voiceQualityScoreService.adjustByInferenceResult(request.getVoiceName(), false, "sync_synthesize_text_ref_error");
                return ResponseEntity.internalServerError().build();
            }

            byte[] audioData = java.util.Base64.getDecoder().decode(responseVO.getAudioData());
            voiceQualityScoreService.adjustByInferenceResult(request.getVoiceName(), true, "sync_synthesize_text_ref");

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.parseMediaType("audio/wav"));
            String filename = (responseVO.getVoiceName() != null && !responseVO.getVoiceName().isBlank())
                    ? responseVO.getVoiceName()
                    : "ref";
            String encodedFilename = java.net.URLEncoder.encode(filename + "_output.wav", StandardCharsets.UTF_8)
                    .replace("+", "%20");
            headers.setContentDisposition(
                    ContentDisposition.inline()
                            .filename(encodedFilename, StandardCharsets.UTF_8)
                            .build()
            );

            return ResponseEntity.ok().headers(headers).body(audioData);
        } catch (Exception e) {
            log.error("synthesizeTextWithRefId failed", e);
            voiceQualityScoreService.adjustByInferenceResult(request.getVoiceName(), false, "sync_synthesize_text_ref_exception");
            return ResponseEntity.internalServerError().build();
        } finally {
            BaseContext.removeCurrentId();
        }
    }

    @PostMapping(value = "/synthesize", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<byte[]> synthesize(
            @RequestParam("voiceName") String voiceName,
            @RequestPart("ttsTextFile") MultipartFile ttsTextFile
    ) {
        try {
            String ttsText = new String(IOUtils.toByteArray(ttsTextFile.getInputStream()), StandardCharsets.UTF_8);
            byte[] audioData = voiceCloneService.synthesize(voiceName, ttsText);
            voiceQualityScoreService.adjustByInferenceResult(voiceName, true, "sync_synthesize");

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.parseMediaType("audio/wav"));
            String encodedFilename = java.net.URLEncoder.encode(voiceName + "_output.wav", StandardCharsets.UTF_8)
                    .replace("+", "%20");
            headers.setContentDisposition(
                    ContentDisposition.attachment()
                            .filename(encodedFilename, StandardCharsets.UTF_8)
                            .build()
            );
            return ResponseEntity.ok().headers(headers).body(audioData);
        } catch (Exception e) {
            log.error("synthesize failed", e);
            voiceQualityScoreService.adjustByInferenceResult(voiceName, false, "sync_synthesize_exception");
            return ResponseEntity.internalServerError().build();
        }
    }

    @PostMapping(value = "/synthesize-stream",
            consumes = {MediaType.TEXT_EVENT_STREAM_VALUE, MediaType.TEXT_PLAIN_VALUE},
            produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> synthesizeStream(
            @RequestParam(value = "voiceName", required = false) String voiceName,
            @RequestParam(value = "voiceAssetId", required = false) String voiceAssetId,
            @RequestBody Flux<String> textStream,
            @RequestHeader(value = "X-INTERNAL", required = false) String internalFlag,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId) {

        if (!isInternalRequest(internalFlag)) {
            return Flux.error(new VoiceServiceException(
                    VoiceErrorEnum.PARAM_VALIDATION_FAILED,
                    "internal-only endpoint"));
        }

        String effectiveVoiceName = voiceName;
        if ((voiceName == null || voiceName.trim().isEmpty()) && voiceAssetId != null && !voiceAssetId.isBlank()) {
            effectiveVoiceName = voiceAssetId;
            log.info("voice stream using voiceAssetId as voiceName: {}", voiceAssetId);
        } else if (voiceName == null || voiceName.trim().isEmpty()) {
            effectiveVoiceName = "default";
        }

        if (effectiveVoiceName == null || effectiveVoiceName.trim().isEmpty()) {
            return Flux.error(new VoiceServiceException(VoiceErrorEnum.VOICE_NAME_EMPTY));
        }

        final String finalEffectiveVoiceName = effectiveVoiceName;
        return voiceCloneService.synthesizeStream(finalEffectiveVoiceName, textStream, traceId, sessionId, turnId)
                .doOnComplete(() -> voiceQualityScoreService.adjustByInferenceResult(finalEffectiveVoiceName, true, "stream_synthesize_complete"))
                .doOnError(error -> log.error("stream synth failed", error))
                .onErrorResume(error -> {
                    voiceQualityScoreService.adjustByInferenceResult(finalEffectiveVoiceName, false, "stream_synthesize_error");
                    String code = "VOICE_STREAM_FAILED";
                    String message = error.getMessage() == null ? "voice stream failed" : error.getMessage();

                    if (!"default".equalsIgnoreCase(finalEffectiveVoiceName)
                            && message.toLowerCase().contains("no audio chunks")) {
                        code = "VOICE_NOT_AVAILABLE";
                        message = "voice_not_available:" + finalEffectiveVoiceName;
                    } else if (message.contains("voice_not_available")) {
                        code = "VOICE_NOT_AVAILABLE";
                    }

                    String escaped = message
                            .replace("\\", "\\\\")
                            .replace("\"", "\\\"");
                    String payload = String.format(
                            "data: {\"type\":\"error\",\"code\":\"%s\",\"voiceName\":\"%s\",\"message\":\"%s\"}\n\n",
                            code,
                            finalEffectiveVoiceName,
                            escaped
                    );
                    return Flux.just(payload);
                });
    }

    @PostMapping(value = "/recognize", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<JsonNode> recognizeAudio(
            @RequestPart("audioFile") MultipartFile audioFile
    ) {
        try {
            File tmp = File.createTempFile("recognize-", ".wav");
            audioFile.transferTo(tmp);
            JsonNode result = voiceCloneService.recognizeAudio(tmp);
            tmp.delete();
            return result != null ? ResponseEntity.ok(result) : ResponseEntity.internalServerError().build();
        } catch (Exception e) {
            log.error("ASR recognize failed", e);
            return ResponseEntity.internalServerError().build();
        }
    }

    @PostMapping(value = "/synthesize-stream", consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<String> synthesizeStream(
            @Valid @RequestBody SynthesizeRequestDTO request,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId,
            @RequestHeader(value = "X-INTERNAL", required = false) String internalFlag) {
        if (!isInternalRequest(internalFlag)) {
            return Flux.error(new VoiceServiceException(
                    VoiceErrorEnum.PARAM_VALIDATION_FAILED,
                    "internal-only endpoint"));
        }

        final String requestVoiceName = (request.getVoiceName() == null || request.getVoiceName().isBlank())
                ? "default"
                : request.getVoiceName();

        return voiceCloneService.synthesizeStream(requestVoiceName, request.getText(), traceId, sessionId, turnId)
                .doOnComplete(() -> voiceQualityScoreService.adjustByInferenceResult(requestVoiceName, true, "stream_synthesize_complete_json"))
                .onErrorResume(error -> {
                    voiceQualityScoreService.adjustByInferenceResult(requestVoiceName, false, "stream_synthesize_error_json");
                    String code = "VOICE_STREAM_FAILED";
                    String message = error.getMessage() == null ? "voice stream failed" : error.getMessage();

                    if (error instanceof WebClientResponseException webEx) {
                        String body = webEx.getResponseBodyAsString();
                        if (webEx.getStatusCode().value() == 422 || (body != null && body.contains("voice_not_available"))) {
                            code = "VOICE_NOT_AVAILABLE";
                            message = body == null || body.isBlank() ? "voice_not_available:" + requestVoiceName : body;
                        }
                    } else if (message.contains("voice_not_available")) {
                        code = "VOICE_NOT_AVAILABLE";
                    }

                    String escaped = message
                            .replace("\\", "\\\\")
                            .replace("\"", "\\\"");
                    String payload = String.format(
                            "data: {\"type\":\"error\",\"code\":\"%s\",\"voiceName\":\"%s\",\"message\":\"%s\"}\n\n",
                            code,
                            requestVoiceName,
                            escaped
                    );
                    return Flux.just(payload);
                });
    }

    private boolean isInternalRequest(String internalFlag) {
        return internalFlag != null && ("1".equals(internalFlag) || "true".equalsIgnoreCase(internalFlag));
    }

    private void bindUserContext(String userId, String authorization) {
        if (userId != null) {
            try {
                BaseContext.setCurrentId(UuidUtils.parseLenient(userId));
            } catch (Exception e) {
                log.debug("Failed to parse user ID: {}", userId, e);
            }
        }
        if ((userId == null || userId.isBlank()) && authorization != null && authorization.startsWith("Bearer ")) {
            try {
                String token = authorization.substring(7);
                var decoded = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
                String uidStr = decoded.getClaim(JwtClaimsConstant.USER_ID).asString();
                if (uidStr != null) {
                    BaseContext.setCurrentId(UuidUtils.parseLenient(uidStr));
                }
            } catch (Exception e) {
                log.debug("Failed to bind user context from token: {}", authorization.substring(0, Math.min(10, authorization.length())), e);
            }
        }
    }
}
