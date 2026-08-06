package com.echoes.voice.domain.inference.service.impl;

import com.echoes.voice.domain.inference.client.EchoesAiClient;
import com.echoes.voice.domain.inference.entity.dto.CloneRequestDTO;
import com.echoes.voice.domain.inference.entity.dto.SynthesizeRefRequestDTO;
import com.echoes.voice.domain.inference.entity.dto.SynthesizeRequestDTO;
import com.echoes.voice.domain.inference.entity.vo.CloneResponseVO;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.inference.entity.vo.SynthesizeResponseVO;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.inference.service.IVoiceCloneService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.io.File;
 

/**
 * 鐠囶參鐓堕張宥呭鐎圭偟骞囬敍鍫熸＋閻楀牏娲挎潻鐐插嚒缁夊娅庨敍?
 * 瑜版挸澧犳禒鍛箽閻ｆ瑦甯撮崣锝呰埌閹緤绱濈粵澶婄窡閹恒儱鍙?Echoes-AI 缂冩垵鍙уù浣哥础閼宠棄濮忛妴?
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceCloneServiceImpl implements IVoiceCloneService {

    private final EchoesAiClient echoesAiClient;
    @SuppressWarnings("unused")
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static VoiceServiceException unavailable() {
        return new VoiceServiceException(
                VoiceErrorEnum.SERVICE_UNAVAILABLE,
                "Direct integration removed; use Echoes-AI gateway.");
    }

    @Override
    public CloneResponseVO cloneSimple(CloneRequestDTO request) {
        log.warn("cloneSimple called but direct integration has been removed.");
        CloneResponseVO response = new CloneResponseVO();
        response.setSuccess(false);
        return response;
    }

    @Override
    public byte[] clone(CloneRequestDTO request) {
        log.warn("clone called but direct integration has been removed.");
        throw unavailable();
    }

    @Override
    public SynthesizeResponseVO synthesizeText(SynthesizeRequestDTO request, String traceId, String sessionId, String turnId) {
        if (request == null || request.getText() == null || request.getText().isBlank()) {
            throw new VoiceServiceException(VoiceErrorEnum.TEXT_EMPTY, "text is required");
        }

        byte[] audio = echoesAiClient.ttsSync(request.getText(), null, traceId, sessionId, turnId);
        if (audio == null || audio.length == 0) {
            throw new VoiceServiceException(VoiceErrorEnum.SYNTHESIS_FAILED, "Echoes-AI returned empty audio");
        }

        SynthesizeResponseVO response = new SynthesizeResponseVO();
        response.setSuccess(true);
        response.setAudioData(java.util.Base64.getEncoder().encodeToString(audio));
        response.setVoiceName(request.getVoiceName());
        return response;
    }

    @Override
    public SynthesizeResponseVO synthesizeTextWithRefId(SynthesizeRefRequestDTO request, String traceId, String sessionId, String turnId) {
        if (request == null || request.getText() == null || request.getText().isBlank()) {
            throw new VoiceServiceException(VoiceErrorEnum.TEXT_EMPTY, "text is required");
        }
        if (request.getRefId() == null || request.getRefId().isBlank()) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "refId is required");
        }

        byte[] audio = echoesAiClient.ttsSync(request.getText(), request.getRefId(), traceId, sessionId, turnId);
        if (audio == null || audio.length == 0) {
            throw new VoiceServiceException(VoiceErrorEnum.SYNTHESIS_FAILED, "Echoes-AI returned empty audio");
        }

        SynthesizeResponseVO response = new SynthesizeResponseVO();
        response.setSuccess(true);
        response.setAudioData(java.util.Base64.getEncoder().encodeToString(audio));
        response.setVoiceName(request.getVoiceName());
        return response;
    }

    @Override
    public byte[] synthesize(String voiceName, String ttsText) {
        log.warn("synthesize called but direct integration has been removed.");
        throw unavailable();
    }

    @Override
    public Flux<String> synthesizeStream(String voiceName, Flux<String> textStream) {
        return synthesizeStream(voiceName, textStream, null, null, null);
    }

    @Override
    public Flux<String> synthesizeStream(String voiceName, Flux<String> textStream, String traceId, String sessionId, String turnId) {
        Flux<String> cleanedTextStream = textStream
                .map(text -> text == null ? "" : text.trim())
                .map(this::stripSseDataPrefix)
                .filter(text -> !text.isBlank())
                .doOnNext(text -> log.info(
                        "voice-stream incoming chunk, len={}, preview={}",
                        text.length(),
                        text.length() > 80 ? text.substring(0, 80) + "..." : text));

        return echoesAiClient
                .synthesizeStream(cleanedTextStream, voiceName, traceId, sessionId, turnId)
                .doOnSubscribe(s -> log.info("voice-stream subscribed, voiceName={}, mode=true-stream-bridge", voiceName))
                .doOnComplete(() -> log.info("voice-stream completed, voiceName={}", voiceName))
                .doOnError(e -> log.error(
                        "voice-stream pipeline failed, voiceName={}, err={}",
                        voiceName,
                        e.getMessage(),
                        e));
    }

    private String stripSseDataPrefix(String raw) {
        if (raw == null) {
            return "";
        }
        String s = raw.trim();
        if (s.startsWith("data:")) {
            return s.substring(5).trim();
        }
        return s;
    }


    @Override
    public Flux<String> synthesizeStream(String voiceName, String text, String traceId, String sessionId, String turnId) {
        if (text == null || text.isBlank()) {
            return Flux.error(new VoiceServiceException(VoiceErrorEnum.TEXT_EMPTY));
        }
        return echoesAiClient.synthesizeStream(text, voiceName, traceId, sessionId, turnId);
    }

    @Override
    public JsonNode recognizeAudio(File audioFile) {
        log.warn("recognizeAudio called but direct integration has been removed.");
        throw unavailable();
    }

    @Override
    public JsonNode listReferenceAudios() {
        log.warn("listReferenceAudios called but direct integration has been removed.");
        return null;
    }

    @Override
    public JsonNode listVoices() {
        log.warn("listVoices called but direct integration has been removed.");
        return null;
    }
}
