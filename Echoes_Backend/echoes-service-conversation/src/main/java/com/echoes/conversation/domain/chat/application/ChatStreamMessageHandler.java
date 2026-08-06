package com.echoes.conversation.domain.chat.application;

import com.echoes.conversation.domain.chat.client.VoiceServiceWebClient;
import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.service.IChatMessageService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import reactor.core.scheduler.Schedulers;

import java.util.UUID;
import java.util.List;
import java.io.ByteArrayOutputStream;
import java.io.IOException;

/**
 * 流式聊天消息处理器
 * 负责消息处理、幂等性校验、消息持久化、音频上传
 */
@Slf4j
@Component
public class ChatStreamMessageHandler {

    private final IChatMessageService chatMessageService;
    private final VoiceServiceWebClient voiceServiceWebClient;
    private final JdbcTemplate jdbcTemplate;
    private final ChatStreamVoiceSynthesizer voiceSynthesizer;
    private final ChatStreamSSEFormatter sseFormatter;

    public ChatStreamMessageHandler(
            IChatMessageService chatMessageService,
            VoiceServiceWebClient voiceServiceWebClient,
            JdbcTemplate jdbcTemplate,
            ChatStreamVoiceSynthesizer voiceSynthesizer,
            ChatStreamSSEFormatter sseFormatter) {
        this.chatMessageService = chatMessageService;
        this.voiceServiceWebClient = voiceServiceWebClient;
        this.jdbcTemplate = jdbcTemplate;
        this.voiceSynthesizer = voiceSynthesizer;
        this.sseFormatter = sseFormatter;
    }

    /**
     * 处理流式聊天完成后的逻辑
     */
    public Runnable handleOnComplete(
            StringBuilder fullContentAccumulator,
            List<byte[]> streamedAudioChunks,
            UUID sessionId,
            String turnId,
            String traceId,
            UUID userId) {

        return () -> {
            try {
                final String assistantFinalContentInitial = fullContentAccumulator.toString();
                final String assistantFinalContent = (assistantFinalContentInitial == null || assistantFinalContentInitial.isBlank())
                        ? "[Audio Response]"
                        : assistantFinalContentInitial;

                log.info("chat-stream finalContent length: {}, preview: {}",
                        assistantFinalContent.length(),
                        assistantFinalContent.length() > 200 ? assistantFinalContent.substring(0, 200) + "..." : assistantFinalContent);

                // Persist assistant message
                var savedMsg = chatMessageService.saveAssistantMessage(sessionId, assistantFinalContent, null);
                try {
                    chatMessageService.updateMessageAudioUrl(savedMsg.getId(), savedMsg.getAudioUrl() != null ? savedMsg.getAudioUrl() : null);
                } catch (Exception e) {
                    log.debug("Post-save session sync/updateMessageAudioUrl skipped or failed: {}", e.getMessage());
                }

                // Assemble and upload audio
                handleAudioUpload(savedMsg, sessionId, turnId, traceId, userId, streamedAudioChunks, assistantFinalContent);

            } catch (Exception e) {
                log.error("Turn completion failed for turnId: {}", turnId, e);
            }
        };
    }

    /**
     * 处理音频上传
     */
    private void handleAudioUpload(
            com.echoes.conversation.domain.chat.entity.po.ChatMessage savedMsg,
            UUID sessionId,
            String turnId,
            String traceId,
            UUID userId,
            List<byte[]> streamedAudioChunks,
            String assistantFinalContent) {

        try {
            byte[] wavBytes = null;
            if (streamedAudioChunks != null && !streamedAudioChunks.isEmpty()) {
                try {
                    wavBytes = voiceSynthesizer.assembleWavFromChunks(streamedAudioChunks, 24000);
                } catch (Exception e) {
                    log.debug("Assembling WAV from streamed chunks failed: {}", e.getMessage());
                    // Fallback to naive concatenation
                    ByteArrayOutputStream baos = new ByteArrayOutputStream();
                    try {
                        for (byte[] chunkBytes : streamedAudioChunks) {
                            if (chunkBytes != null && chunkBytes.length > 0) {
                                baos.write(chunkBytes);
                            }
                        }
                        wavBytes = baos.toByteArray();
                    } finally {
                        try {
                            baos.close();
                        } catch (IOException ex) {
                            log.debug("Failed to close ByteArrayOutputStream: {}", ex.getMessage());
                        }
                    }
                }
                log.info("Using buffered streamed audio for upload, assembled bytes={}", wavBytes == null ? 0 : wavBytes.length);
            } else {
                // Fallback: synthesize final audio
                handleFallbackSynthesis(assistantFinalContent, traceId, sessionId, turnId);
            }

            if (wavBytes != null && wavBytes.length > 0) {
                uploadAndPersistAudio(wavBytes, sessionId, savedMsg.getId(), turnId, traceId, userId);
            }
        } catch (Exception ex) {
            log.warn("生成或上传最终音频失败（允许降级），turnId: {}, err: {}", turnId, ex.getMessage());
        }
    }

    /**
     * 回退合成
     */
    private void handleFallbackSynthesis(String content, String traceId, UUID sessionId, String turnId) {
        try {
            Schedulers.boundedElastic().schedule(() -> {
                try {
                    voiceServiceWebClient.synthesizeText(content, "default", traceId, sessionId.toString(), turnId)
                            .doOnError(e -> log.debug("Fallback synth failed: {}", e.getMessage()))
                            .subscribe();
                } catch (Exception e) {
                    log.debug("Fallback synth failed: {}", e.getMessage());
                }
            });
        } catch (Exception e) {
            log.debug("Fallback synth scheduling failed: {}", e.getMessage());
        }
    }

    /**
     * 上传并持久化音频
     */
    private void uploadAndPersistAudio(
            byte[] finalWav,
            UUID sessionId,
            UUID savedMsgId,
            String turnId,
            String traceId,
            UUID userId) {

        Schedulers.boundedElastic().schedule(() -> {
            try {
                String audioRef = java.util.UUID.randomUUID().toString();
                String objectName = String.format("audio/%s/%s/%s/%s.wav",
                        sessionId != null ? sessionId.toString() : "unknown",
                        savedMsgId != null ? savedMsgId.toString() : "msg",
                        turnId != null ? turnId : "turn",
                        audioRef);

                // Upload to voice service
                JsonNode uploadResult = voiceServiceWebClient.uploadObject(finalWav, objectName, traceId, sessionId.toString(), turnId).block();
                String storageKey = null;
                if (uploadResult != null && uploadResult.has("storage_key")) {
                    storageKey = uploadResult.get("storage_key").asText();
                }

                // Persist to MySQL
                persistAudioAsset(storageKey, objectName, audioRef, userId, sessionId, turnId, savedMsgId, finalWav.length);

                // Update message audio URL
                String audioEndpoint = "/api/conversation/audio/" + audioRef;
                try {
                    chatMessageService.updateMessageAudioUrl(savedMsgId, audioEndpoint);
                } catch (Exception e) {
                    log.warn("保存 audio ref 到 ChatMessage 失败：{}", e.getMessage());
                }

            } catch (Exception e) {
                log.warn("Background upload or persist failed for turnId {}: {}", turnId, e.getMessage(), e);
            }
        });
    }

    /**
     * 持久化音频资产到数据库
     */
    private void persistAudioAsset(
            String storageKey,
            String objectName,
            String audioRef,
            UUID userId,
            UUID sessionId,
            String turnId,
            UUID savedMsgId,
            int sizeBytes) {

        try {
            String sql = "INSERT INTO audio_asset (audio_ref, storage_key, format, duration_ms, size_bytes, sha256, owner_user_id, conversation_id, turn_id, message_id, create_time) " +
                    "VALUES (?,?,?,?,?,?,UNHEX(REPLACE(?, '-', '')),UNHEX(REPLACE(?, '-', '')),?, ?, NOW())";
            Object[] params = new Object[] {
                    audioRef,
                    storageKey != null ? storageKey : objectName,
                    "wav",
                    null,
                    sizeBytes,
                    null,
                    userId != null ? userId.toString() : null,
                    sessionId,
                    turnId,
                    savedMsgId != null ? savedMsgId.toString() : null
            };
            jdbcTemplate.update(sql, params);
        } catch (Exception e) {
            log.warn("写入 audio_asset 失败，storageKey={}, userId={}, conversationId={}, turnId={}, messageId={}",
                    storageKey != null ? storageKey : objectName,
                    userId,
                    sessionId,
                    turnId,
                    savedMsgId,
                    e);
        }
    }

    /**
     * 计算请求哈希（用于幂等性）
     */
    public byte[] computePayloadHash(ChatRequestDTO request) {
        try {
            String canonical = request.getSessionId() + "|" + request.getTurnId() + "|" + request.getMessage();
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            return digest.digest(canonical.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        } catch (Exception e) {
            log.debug("Failed to compute payload hash: {}", e.getMessage());
            return new byte[0];
        }
    }
}
