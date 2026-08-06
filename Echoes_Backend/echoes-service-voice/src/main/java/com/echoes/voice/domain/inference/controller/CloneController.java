package com.echoes.voice.domain.inference.controller;

import com.echoes.context.BaseContext;
import com.echoes.utils.UuidUtils;
import com.echoes.voice.domain.inference.entity.dto.CloneRequestDTO;
import com.echoes.voice.domain.inference.entity.vo.CloneResponseVO;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.inference.service.IVoiceCloneService;
import com.echoes.voice.config.JwtProperties;
import com.echoes.voice.common.constants.JwtClaimsConstant;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.io.IOUtils;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;

/**
 * 语音克隆控制器
 * 提供音色克隆、语音合成、ASR识别等接口
 */
@RestController
@RequestMapping("/internal/voice")
@RequiredArgsConstructor
@Slf4j
public class CloneController {
    private final IVoiceCloneService voiceCloneService;
    private final JwtProperties jwtProperties;

    /**
     * 声纹克隆接口 - 适合前端调用（支持字符串参数）
     * 返回 JSON 格式，包含音频数据（base64）和音色信息
     */
    @PostMapping(value = "/assets/clone-simple", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<CloneResponseVO> cloneSimple(
            @RequestPart("promptWav") MultipartFile promptWav,
            @RequestParam("promptText") String promptText,
            @RequestParam("ttsText") String ttsText,
            @RequestParam(name = "speakerName", required = false) String speakerName,
            @RequestHeader(value = "X-USER-ID", required = false) String userId,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        try {
            if (userId != null) {
                try {
                    BaseContext.setCurrentId(UuidUtils.parseLenient(userId));
                } catch (Exception e) {
                    log.debug("解析 userId 失败，继续处理：{}", userId);
                }
            }
            // fallback via Authorization
            if ((userId == null || userId.isBlank()) && authorization != null && authorization.startsWith("Bearer ")) {
                try {
                    String token = authorization.substring(7);
                    var decoded = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
                    String uidStr = decoded.getClaim(JwtClaimsConstant.USER_ID).asString();
                    if (uidStr != null) {
                        BaseContext.setCurrentId(UuidUtils.parseLenient(uidStr));
                        userId = uidStr;
                    }
                } catch (Exception e) {
                    log.debug("解析 JWT Token 中的 userId 失败：{}", e.getMessage());
                }
            }

            CloneRequestDTO request = new CloneRequestDTO();
            request.setPromptWav(promptWav);
            request.setPromptText(promptText);
            request.setTtsText(ttsText);
            request.setSpeakerName(speakerName);
            try { request.setUserId(userId != null ? UuidUtils.parseLenient(userId) : null); } catch (Exception e) {
                log.debug("设置 userId 失败：{}", userId);
            }

            CloneResponseVO response = voiceCloneService.cloneSimple(request);

            if (response.getSuccess() == null || !response.getSuccess()) {
                return ResponseEntity.internalServerError().body(response);
            }

            return ResponseEntity.ok(response);
        } catch (VoiceServiceException e) {
            log.error("语音克隆失败", e);
            CloneResponseVO errorVO = new CloneResponseVO();
            errorVO.setSuccess(false);
            return ResponseEntity.badRequest().body(errorVO);
        } catch (Exception e) {
            log.error("语音克隆异常", e);
            CloneResponseVO errorVO = new CloneResponseVO();
            errorVO.setSuccess(false);
            return ResponseEntity.internalServerError().body(errorVO);
        } finally {
            BaseContext.removeCurrentId();
        }
    }

    /**
     * 语音克隆接口 - 返回WAV音频文件
     */
    @PostMapping(value = "/assets/clone", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<byte[]> clone(
            @RequestPart("promptWav") MultipartFile promptWav,
            @RequestPart("ttsTextFile") MultipartFile ttsTextFile,
            @RequestPart("promptText") String promptText,
            @RequestPart(name = "speakerName", required = false) String speakerName,
            @RequestHeader(value = "X-USER-ID", required = false) String userId,
            @RequestHeader(value = "Authorization", required = false) String authorization) {
        try {
            if (userId != null) {
                try { BaseContext.setCurrentId(UuidUtils.parseLenient(userId)); } catch (Exception e) {
                    log.debug("解析 userId 失败：{}", userId);
                }
            }
            if ((userId == null || userId.isBlank()) && authorization != null && authorization.startsWith("Bearer ")) {
                try {
                    String token = authorization.substring(7);
                    var decoded = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
                    String uidStr = decoded.getClaim(JwtClaimsConstant.USER_ID).asString();
                    if (uidStr != null) {
                        BaseContext.setCurrentId(UuidUtils.parseLenient(uidStr));
                        userId = uidStr;
                    }
                } catch (Exception e) {
                    log.debug("解析 JWT Token 中的 userId 失败：{}", e.getMessage());
                }
            }

            String ttsText = new String(IOUtils.toByteArray(ttsTextFile.getInputStream()), StandardCharsets.UTF_8);

            CloneRequestDTO request = new CloneRequestDTO();
            request.setPromptWav(promptWav);
            request.setPromptText(promptText);
            request.setTtsText(ttsText);
            request.setSpeakerName(speakerName);
            try { request.setUserId(userId != null ? UuidUtils.parseLenient(userId) : null); } catch (Exception e) {
                log.debug("设置 userId 失败：{}", userId);
            }

            byte[] wav = voiceCloneService.clone(request);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.parseMediaType("audio/wav"));
            headers.setContentDisposition(ContentDisposition.attachment().filename("result.wav").build());

            return ResponseEntity.ok().headers(headers).body(wav);
        } catch (Exception e) {
            log.error("Voice clone failed", e);
            return ResponseEntity.internalServerError().build();
        } finally {
            BaseContext.removeCurrentId();
        }
    }

    /**
     * 列出参考音频
     */
    @GetMapping("/assets/reference-audios")
    public ResponseEntity<JsonNode> listReferenceAudios() {
        JsonNode result = voiceCloneService.listReferenceAudios();
        return ResponseEntity.ok(result);
    }

    /**
     * 列出所有声音
     */
    @GetMapping("/assets/voices")
    public ResponseEntity<JsonNode> listVoices() {
        JsonNode result = voiceCloneService.listVoices();
        return ResponseEntity.ok(result);
    }
}