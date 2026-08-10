package com.echoes.conversation.domain.chat.application;

import com.echoes.conversation.domain.chat.client.VoiceServiceWebClient;
import com.echoes.conversation.domain.chat.client.feign.VoiceServiceUserDefaultClient;
import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;
import com.echoes.conversation.domain.chat.repository.ConversationSessionRepository;
import com.echoes.conversation.domain.chat.service.IChatMessageService;
import com.echoes.conversation.domain.chat.service.ITurnService;
import com.echoes.utils.UuidUtils;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicReference;

/**
 * 流式聊天应用服务（主协调器）
 * 协调各子服务完成流式聊天功能
 *
 * 依赖的子服务：
 * - ChatStreamSessionManager: 会话管理
 * - ChatStreamMessageHandler: 消息处理
 * - ChatStreamVoiceSynthesizer: 语音合成
 * - ChatStreamSSEFormatter: SSE 格式化
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatStreamApplicationService {

    private final VoiceServiceWebClient voiceServiceWebClient;
    private final VoiceServiceUserDefaultClient voiceServiceUserDefaultClient;
    private final IChatMessageService chatMessageService;
    private final ConversationSessionRepository conversationSessionRepository;
    private final ITurnService turnService;

    private final ChatStreamSessionManager sessionManager;
    private final ChatStreamMessageHandler messageHandler;
    private final ChatStreamVoiceSynthesizer voiceSynthesizer;
    private final ChatStreamSSEFormatter sseFormatter;

    public Flux<String> streamChat(ChatRequestDTO request) {
        String traceId = UUID.randomUUID().toString();
        UUID sessionId = sessionManager.parseSessionId(request.getSessionId());
        String turnId = request.getTurnId();

        // 1) 基础校验
        if (turnId == null || turnId.isBlank()) {
            return Flux.just(sseFormatter.formatSSEAndPersist(
                    "error",
                    sseFormatter.buildErrorData("TURN_ID_REQUIRED", "Turn ID is required", "request_validation", false, 400, null, "Provide a valid turnId and retry."),
                    traceId, request.getSessionId(), null, "1.0"));
        }

        // 2) 开始 Turn (幂等性校验)
        String idempotencyKey = request.getIdempotencyKey() != null ? request.getIdempotencyKey() : turnId;
        byte[] payloadHash = messageHandler.computePayloadHash(request);

        // 解析用户 ID 和音色 ID
        AtomicReference<UUID> userIdRef = resolveUserId(request.getSysUserId(), sessionId);
        AtomicReference<UUID> voiceIdRef = resolveVoiceId(userIdRef);

        // 启动回合
        ConversationTurn turn = startTurnWithValidation(sessionId, turnId, userIdRef, idempotencyKey, payloadHash);
        if (turn == null) {
            return Flux.just(sseFormatter.formatSSEAndPersist(
                    "error",
                    sseFormatter.buildErrorData("TURN_INIT_FAILED", "Turn init failed", "turn_init", true, 500, null, "Start a new turn."),
                    traceId, request.getSessionId(), request.getTurnId(), "1.0"));
        }

        if ("SUCCESS".equals(turn.getStatus())) {
            return Flux.just(sseFormatter.formatSSEAndPersist(
                    "error",
                    sseFormatter.buildErrorData("TURN_ALREADY_COMPLETED", "Turn already completed (REPLAY not supported yet)", "turn_init", false, 409, null, "Start a new turn."),
                    traceId, request.getSessionId(), request.getTurnId(), "1.0"));
        }

        // 3) 用户 ID 校验
        String protocolVersion = "1.0";
        if (userIdRef.get() == null) {
            return Flux.just(sseFormatter.formatSSEAndPersist(
                    "error",
                    sseFormatter.buildErrorData("MISSING_USER_ID", "X-USER-ID is required for voice stream", "voice_precheck", false, 400, null, "Retry with authenticated user context."),
                    traceId, request.getSessionId(), turnId, protocolVersion));
        }

        // 4) 执行流式聊天
        return executeStreamChat(request, traceId, sessionId, turnId, userIdRef, voiceIdRef, protocolVersion);
    }

    /**
     * 解析用户 ID：优先从 BaseContext（网关注入的 X-USER-ID），fallback 到 session 表查询
     */
    private AtomicReference<UUID> resolveUserId(String sysUserId, UUID sessionId) {
        AtomicReference<UUID> userIdRef = new AtomicReference<>(null);

        // 1. 优先从 BaseContext 获取（UserContextFilter 已从 X-USER-ID 设置）
        UUID contextUserId = com.echoes.context.BaseContext.getCurrentId();
        if (contextUserId != null) {
            userIdRef.set(contextUserId);
            log.debug("Resolved userId from BaseContext: {}", contextUserId);
            return userIdRef;
        }

        // 2. Fallback: 从 conversation_session 表查询（兜底逻辑，正常流程不应走到这里）
        if (sessionId != null) {
            try {
                var conv = conversationSessionRepository.findById(sessionId).orElse(null);
                if (conv != null && (conv.getIsDeleted() == null || conv.getIsDeleted() == 0)) {
                    userIdRef.set(conv.getUserId());
                    log.debug("Resolved userId from conversation_session fallback: sessionId={}, userId={}",
                              sessionId, conv.getUserId());
                }
            } catch (Exception e) {
                log.error("Failed to resolve userId from conversation_session: sessionId={}", sessionId, e);
            }
        }

        if (userIdRef.get() == null) {
            log.warn("resolveUserId: userId is null after all attempts (sysUserId={}, sessionId={})",
                     sysUserId, sessionId);
        }

        return userIdRef;
    }

    /**
     * 解析默认音色
     */
    private AtomicReference<UUID> resolveVoiceId(AtomicReference<UUID> userIdRef) {
        AtomicReference<UUID> voiceIdRef = new AtomicReference<>(null);

        if (voiceIdRef.get() == null && userIdRef.get() != null) {
            try {
                var response = voiceServiceUserDefaultClient.getUserDefaultVoice(userIdRef.get());
                if (response.getBody() != null) {
                    voiceIdRef.set(response.getBody());
                    log.info("使用用户级默认音色：{}", response.getBody());
                }
            } catch (Exception e) {
                log.debug("Failed to resolve voice from voice service: {}", e.getMessage());
            }
        }

        return voiceIdRef;
    }

    /**
     * 开始回合（带错误处理）
     */
    private ConversationTurn startTurnWithValidation(
            UUID sessionId, String turnId, AtomicReference<UUID> userIdRef,
            String idempotencyKey, byte[] payloadHash) {
        try {
            ConversationTurn turn = turnService.startTurn(sessionId, turnId, userIdRef.get(), idempotencyKey, payloadHash);
            if ("SUCCESS".equals(turn.getStatus())) {
                return turn;
            }
            return turn;
        } catch (IllegalStateException e) {
            log.error("Turn init rejected: {}", e.getMessage());
            return null;
        } catch (Exception e) {
            log.error("Start Turn failed", e);
            return null;
        }
    }

    /**
     * 执行流式聊天
     */
    private Flux<String> executeStreamChat(
            ChatRequestDTO request,
            String traceId,
            UUID sessionId,
            String turnId,
            AtomicReference<UUID> userIdRef,
            AtomicReference<UUID> voiceIdRef,
            String protocolVersion) {

        StringBuilder fullContentAccumulator = new StringBuilder();
        List<byte[]> streamedAudioChunks = new CopyOnWriteArrayList<>();

        String voiceName = voiceIdRef.get() != null ? voiceIdRef.get().toString() : "default";
        log.info("使用音色进行合成：{}, sessionId={}", voiceName, sessionId);

        // 获取 AI 文本流
        Flux<String> aiTextFlux = chatMessageService.chatStream(request)
                .doOnNext(chunk -> {
                    if (chunk != null) fullContentAccumulator.append(chunk);
                })
                .publish()
                .autoConnect(2);

        // 文本事件
        Flux<String> textEvents = aiTextFlux.map(chunk ->
                sseFormatter.formatSSEAndPersist("message.delta", chunk, traceId, sessionId.toString(), turnId, protocolVersion));

        // 音频事件
        Flux<String> audioEvents = voiceServiceWebClient.synthesizeStream(
                        voiceName,
                        aiTextFlux,
                        traceId,
                        sessionId.toString(),
                        turnId,
                        userIdRef.get().toString())
                .map(audioChunk -> {
                    Object parsed = sseFormatter.parseAudioChunkData(audioChunk);
                    captureAudioChunk(parsed, streamedAudioChunks);
                    return sseFormatter.formatSSEAndPersist("audio_chunk", parsed, traceId, sessionId.toString(), turnId, protocolVersion);
                });

        // 合并流并处理完成逻辑
        return Flux.merge(textEvents, audioEvents)
                .doOnComplete(messageHandler.handleOnComplete(
                        fullContentAccumulator,
                        streamedAudioChunks,
                        sessionId,
                        turnId,
                        traceId,
                        userIdRef.get()))
                .doOnError(error -> {
                    log.error("chat-stream 流式失败", error);
                })
                .onErrorResume(error -> Flux.just(sseFormatter.formatSSEAndPersist(
                        "error",
                        sseFormatter.buildErrorData("VOICE_STREAM_PIPELINE_FAILED", error.getMessage(), "voice_stream", true, 502, null, "Retry later or switch to default voice."),
                        traceId,
                        sessionId.toString(),
                        turnId,
                        protocolVersion)))
                .concatWith(Flux.defer(() -> {
                    String finalContent = fullContentAccumulator.toString();
                    if (finalContent == null) finalContent = "";
                    return Flux.just(
                            sseFormatter.formatSSEAndPersist("message.final", finalContent, traceId, sessionId.toString(), turnId, protocolVersion),
                            sseFormatter.formatSSEAndPersist("end", "finished", traceId, sessionId.toString(), turnId, protocolVersion)
                    );
                }));
    }

    /**
     * 捕获音频块
     */
    private void captureAudioChunk(Object parsed, List<byte[]> streamedAudioChunks) {
        try {
            if (parsed instanceof Map) {
                @SuppressWarnings("unchecked")
                Map<String, Object> audioMap = (Map<String, Object>) parsed;
                Object audioObj = audioMap.get("audio");
                if (audioObj instanceof String) {
                    String b64 = (String) audioObj;
                    if (b64 != null && !b64.isBlank()) {
                        try {
                            byte[] bytes = Base64.getDecoder().decode(b64);
                            streamedAudioChunks.add(bytes);
                        } catch (IllegalArgumentException iae) {
                            log.debug("Failed to decode streamed audio base64 chunk: {}", iae.getMessage());
                        }
                    }
                }
            }
        } catch (Exception e) {
            log.debug("Error while buffering streamed audio chunk: {}", e.getMessage());
        }
    }
}
