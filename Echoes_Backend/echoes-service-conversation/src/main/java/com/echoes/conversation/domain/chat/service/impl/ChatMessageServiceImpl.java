package com.echoes.conversation.domain.chat.service.impl;

import com.echoes.conversation.common.constants.AIChatConstants;
import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.po.ChatMessage;
import com.echoes.conversation.domain.chat.entity.vo.ChatResponseVO;
import com.echoes.conversation.domain.chat.entity.vo.ChatSessionVO;
import com.echoes.conversation.domain.chat.enums.AIChatEnum;
import com.echoes.exception.BusinessException;
import com.echoes.conversation.domain.chat.repository.ChatMessageRepository;
import com.echoes.conversation.domain.chat.repository.ChatSessionRepository;
import com.echoes.conversation.domain.chat.service.IChatMessageService;
import com.echoes.conversation.domain.chat.service.IChatSessionService;
import com.github.f4b6a3.uuid.UuidCreator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import reactor.core.publisher.Flux;

import com.echoes.conversation.domain.chat.entity.po.ChatSession;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import com.echoes.utils.UuidUtils;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import jakarta.servlet.http.HttpServletRequest;
import com.echoes.conversation.config.JwtProperties;

/**
 * 聊天消息服务实现类
 * 负责AI对话消息的创建、查询、反馈等功能
 *
 */
@Slf4j
@Service
public class ChatMessageServiceImpl implements IChatMessageService {

    private final ChatMessageRepository chatMessageRepository;
    private final ChatSessionRepository chatSessionRepository;
    private final IChatSessionService chatSessionService;
    private final ChatClient chatClient;
    private final MongoTemplate mongoTemplate;
    private final RedisTemplate<String, Object> redisTemplate;
    private final com.echoes.conversation.domain.chat.repository.ConversationSessionRepository conversationSessionRepository;
    private final JwtProperties jwtProperties;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public ChatMessageServiceImpl(
            ChatMessageRepository chatMessageRepository,
            ChatSessionRepository chatSessionRepository,
            IChatSessionService chatSessionService,
            @Qualifier("qWenChatClient") ChatClient chatClient,
            MongoTemplate mongoTemplate,
            RedisTemplate<String, Object> redisTemplate,
            com.echoes.conversation.domain.chat.repository.ConversationSessionRepository conversationSessionRepository,
            JwtProperties jwtProperties) {
        this.chatMessageRepository = chatMessageRepository;
        this.chatSessionRepository = chatSessionRepository;
        this.chatSessionService = chatSessionService;
        this.chatClient = chatClient;
        this.mongoTemplate = mongoTemplate;
        this.redisTemplate = redisTemplate;
        this.conversationSessionRepository = conversationSessionRepository;
        this.jwtProperties = jwtProperties;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ChatResponseVO chat(ChatRequestDTO request) {
        ChatSessionVO sessionVO = getOrCreateSession(request);
        UUID sessionId = UuidUtils.parseLenient(sessionVO.getId());

        List<Message> messages = buildContext(sessionId, request);

        String aiResponse = callModel(messages);

        // 先保存用户消息
        ChatMessage userMessage = addUserMessage(sessionId, request.getMessage(), request.getAttachments());

        // 保存AI助手消息，父消息ID为用户消息ID
        ChatMessage assistantMessage = saveAssistantMessage(sessionId, aiResponse, userMessage.getId());

        chatSessionService.updateSessionLastMessage(sessionId, aiResponse);

        ChatResponseVO responseVO = new ChatResponseVO();
        responseVO.setSessionId(UuidUtils.toString(sessionId));
        responseVO.setMessageId(UuidUtils.toString(assistantMessage.getId()));
        responseVO.setContent(aiResponse);
        responseVO.setModel(AIChatConstants.MODEL_QWEN3_MAX);
        responseVO.setTokenCount(assistantMessage.getTokenCount());
        responseVO.setResponseTime(LocalDateTime.now());
        responseVO.setFinished(true);

        return responseVO;
    }

    @Override
    public Flux<String> chatStream(ChatRequestDTO request) {
        ChatSessionVO sessionVO = getOrCreateSession(request);
        UUID sessionId = UuidUtils.parseLenient(sessionVO.getId());

        List<Message> messages = buildContext(sessionId, request);

        addUserMessage(sessionId, request.getMessage(), request.getAttachments());

        StringBuilder fullResponse = new StringBuilder();

        return chatClient
                .prompt()
                .messages(messages)
                .stream()
                .content()
                .doOnNext(fullResponse::append)
                .doOnComplete(() -> {
                    try {
                        // Completion handling for chat stream: saving of assistant message
                        // has been delegated to upper-level application service to avoid duplicate persistence.
                        log.debug("chatStream completed for sessionId: {}, collected-length: {}", sessionId, fullResponse.length());
                    } catch (Exception e) {
                        log.error("chatStream completion handler error: ", e);
                    }
                })
                .doOnError(e -> log.error("流式对话异常，会话ID: {}, 错误信息: ", sessionId, e));
    }

    @Override
    @Transactional(readOnly = true)
    public List<ChatMessage> listMessagesBySessionId(UUID sessionId, Integer limit) {
        if (sessionId == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        if (limit != null && limit > 0) {
            Pageable pageable = PageRequest.of(0, limit);
            return chatMessageRepository.findBySessionIdOrderByCreateTimeAsc(sessionId, pageable).getContent();
        }

        return chatMessageRepository.findBySessionIdOrderByCreateTimeAsc(sessionId);
    }

    @Override
    @Transactional(readOnly = true)
    public ChatMessage getChatMessageById(UUID id) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.MESSAGE_ID_REQUIRED.getCode(), AIChatEnum.MESSAGE_ID_REQUIRED.getMessage());
        }

        return chatMessageRepository.findById(id)
                .orElseThrow(() -> new BusinessException(AIChatEnum.MESSAGE_NOT_EXISTS.getCode(), AIChatEnum.MESSAGE_NOT_EXISTS.getMessage()));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean feedbackMessage(UUID messageId, Integer feedback) {
        if (messageId == null) {
            throw new BusinessException(AIChatEnum.MESSAGE_ID_REQUIRED.getCode(), AIChatEnum.MESSAGE_ID_REQUIRED.getMessage());
        }

        if (feedback == null || (feedback != AIChatConstants.FEEDBACK_LIKE && feedback != AIChatConstants.FEEDBACK_DISLIKE)) {
            throw new BusinessException(AIChatEnum.FEEDBACK_VALUE_INVALID.getCode(), AIChatEnum.FEEDBACK_VALUE_INVALID.getMessage());
        }

        ChatMessage message = chatMessageRepository.findById(messageId)
                .orElseThrow(() -> new BusinessException(AIChatEnum.MESSAGE_NOT_EXISTS.getCode(), AIChatEnum.MESSAGE_NOT_EXISTS.getMessage()));

        message.setIsFeedback(feedback);
        message.setUpdateTime(LocalDateTime.now());
        chatMessageRepository.save(message);

        return true;
    }

    private ChatSessionVO getOrCreateSession(ChatRequestDTO request) {
        if (request.getSessionId() != null) {
            java.util.UUID sid = UuidUtils.parseLenient(request.getSessionId());
            if (sid != null) {
                return chatSessionService.getChatSessionById(sid);
            }
        }
        // Prefer sysUserId passed in the request DTO if present (frontend/gateway may forward it)
        java.util.UUID resolvedUserId = null;
        try {
            if (request.getSysUserId() != null && !request.getSysUserId().isBlank()) {
                resolvedUserId = UuidUtils.parseLenient(request.getSysUserId());
            }
        } catch (Exception e) {
            log.debug("Failed to parse sysUserId from request DTO: {}", e.getMessage());
        }

        // Fallback to headers or Authorization token if DTO did not contain userId
        if (resolvedUserId == null) {
            try {
                ServletRequestAttributes attrs = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
                if (attrs != null) {
                    HttpServletRequest httpReq = attrs.getRequest();
                    String headerUserId = httpReq.getHeader("X-USER-ID");
                    if (headerUserId != null && !headerUserId.isBlank()) {
                        resolvedUserId = UuidUtils.parseLenient(headerUserId);
                    } else {
                        String authorization = httpReq.getHeader("Authorization");
                        if (authorization != null && authorization.startsWith("Bearer ")) {
                            try {
                                String token = authorization.substring(7);
                                var decoded = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
                                String uidStr = decoded.getClaim(com.echoes.conversation.common.constants.JwtClaimsConstant.USER_ID).asString();
                                if (uidStr != null && !uidStr.isBlank()) {
                                    resolvedUserId = UuidUtils.parseLenient(uidStr);
                                }
                            } catch (Exception e) {
                                log.debug("Failed to parse userId from Authorization token in getOrCreateSession: {}", e.getMessage());
                            }
                        }
                    }
                }
            } catch (Exception e) {
                log.debug("Unable to resolve HttpServletRequest for userId resolution: {}", e.getMessage());
            }
        }

        // Try Redis active-session quick lookup to avoid race where Mongo hasn't been created yet
        if (resolvedUserId != null) {
            try {
                String activeKey = "user:active-session:" + resolvedUserId;
                Object cached = redisTemplate.opsForValue().get(activeKey);
                if (cached instanceof String) {
                    java.util.UUID cachedSid = UuidUtils.parseLenient((String) cached);
                    if (cachedSid != null) {
                        try {
                            return chatSessionService.getChatSessionById(cachedSid);
                        } catch (Exception e) {
                            log.debug("Redis-cached sessionId lookup failed, will fallback to create: {}", e.getMessage());
                        }
                    }
                }
            } catch (Exception e) {
                log.debug("Redis lookup for active-session failed: {}", e.getMessage());
            }
        }

        return chatSessionService.addChatSession(null, null, null, resolvedUserId);
    }

    private List<Message> buildContext(UUID sessionId, ChatRequestDTO request) {
        List<Message> messages = new ArrayList<>();

        // System/User messages cannot have null content
        String systemPrompt = AIChatConstants.SYSTEM_PROMPT != null ? AIChatConstants.SYSTEM_PROMPT : "";
        messages.add(new SystemMessage(systemPrompt));

        List<ChatMessage> history = listMessagesBySessionId(sessionId, AIChatConstants.DEFAULT_HISTORY_LIMIT);
        for (ChatMessage msg : history) {
            if (msg == null || msg.getContent() == null) {
                continue;
            }
            if (AIChatConstants.ROLE_USER.equals(msg.getRole())) {
                messages.add(new UserMessage(msg.getContent()));
            } else if (AIChatConstants.ROLE_ASSISTANT.equals(msg.getRole())) {
                messages.add(new AssistantMessage(msg.getContent()));
            } else if (AIChatConstants.ROLE_SYSTEM.equals(msg.getRole())) {
                messages.add(new SystemMessage(msg.getContent()));
            }
        }

        String userContent = request != null && request.getMessage() != null ? request.getMessage() : "";
        messages.add(new UserMessage(userContent));

        return messages;
    }

    private String callModel(List<Message> messages) {
        try {
            // Debug: log outgoing messages summary
            try {
                log.debug("callModel - outgoing messages: {}", messages.stream()
                        .map(m -> m.getClass().getSimpleName() + ":" + (m.toString() == null ? "" : m.toString()))
                        .collect(java.util.stream.Collectors.joining(" | ")));
            } catch (Exception e) {
                log.debug("callModel - failed to stringify messages: {}", e.getMessage());
            }

            // Call model via streaming API and collect chunks to form final content (blocking for sync path)
            try {
                reactor.core.publisher.Flux<String> contentFlux = chatClient
                        .prompt()
                        .messages(messages)
                        .stream()
                        .content();

                java.util.List<String> chunks = contentFlux.collectList().block();
                String content = (chunks == null || chunks.isEmpty()) ? null : String.join("", chunks);
                log.debug("callModel - collected {} chunks, total length: {}", chunks == null ? 0 : chunks.size(),
                        content == null ? 0 : content.length());
                return content;
            } catch (Exception e) {
                log.error("callModel - streaming call failed", e);
                throw e;
            }
        } catch (Exception e) {
            log.error("AI模型调用失败: ", e);
            throw new BusinessException(AIChatEnum.AI_SERVICE_ERROR.getCode(), AIChatEnum.AI_SERVICE_ERROR.getMessage());
        }
    }

    /**
     * 添加用户消息
     * 设置sysUserId、messageIndex、parentMessageId等新增字段
     * 并更新会话的messageCount和totalTokens
     *
     * @param sessionId 会话ID
     * @param content 消息内容
     * @param attachments 附件列表
     * @return 保存的消息实体
     */
    private ChatMessage addUserMessage(UUID sessionId, String content, List<String> attachments) {
        // 获取会话信息
        ChatSession session = chatSessionRepository.findById(sessionId).orElse(null);
        if (session == null) {
            // attempt lazy creation from conversation_session when Mongo session is missing
            try {
                chatSessionService.getChatSessionById(sessionId);
            } catch (BusinessException e) {
                throw e;
            } catch (Exception e) {
                log.warn("Failed to auto-create ChatSession for sessionId {}: {}", sessionId, e.getMessage());
            }
            session = chatSessionRepository.findById(sessionId).orElse(null);
        }
        if (session == null) {
            throw new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage());
        }

        // 计算消息序号：当前会话的消息数量 + 1
        Long currentMessageCount = session.getMessageCount() != null ? session.getMessageCount() : 0L;
        Integer messageIndex = currentMessageCount.intValue() + 1;

        // 获取上一条消息ID作为父消息ID
        UUID parentMessageId = null;
        ChatMessage lastMessage = chatMessageRepository
                .findFirstBySessionIdOrderByCreateTimeDesc(sessionId);
        if (lastMessage != null) {
            parentMessageId = lastMessage.getId();
        }

        // defensive: ensure content is not null to avoid missing field in Mongo
        String safeContent = content == null ? "" : content;
        String safePreview = safeContent.length() > 200 ? safeContent.substring(0, 200) + "..." : safeContent;
        log.info("Preparing to save user message (addUserMessage) - sessionId: {}, messageIndex: {}, preview: {}",
                sessionId, messageIndex, safePreview);

        ChatMessage message = new ChatMessage();
        // use UUID (time-ordered) for message ID
        message.setId(UuidCreator.getTimeOrdered());
        message.setSessionId(sessionId);
        message.setSysUserId(session.getSysUserId());
        message.setParentMessageId(parentMessageId);
        message.setMessageIndex(messageIndex);
        message.setRole(AIChatConstants.ROLE_USER);
        message.setContent(safeContent);
        message.setMessageType(AIChatConstants.MESSAGE_TYPE_TEXT);
        message.setAttachments(attachments);
        message.setIsFeedback(AIChatConstants.FEEDBACK_NONE);
        message.setIsDeleted(AIChatConstants.DELETED_FALSE);
        message.setCreateTime(LocalDateTime.now());
        message.setUpdateTime(LocalDateTime.now());

        ChatMessage savedMessage;
        try {
            log.info("Saving ChatMessage to Mongo (addUserMessage), sessionId: {}, messageIndex: {}, role: {}",
                    sessionId, messageIndex, message.getRole());
            savedMessage = chatMessageRepository.save(message);
        } catch (Exception ex) {
            log.error("保存 ChatMessage 到 Mongo 失败 (addUserMessage), sessionId: {}, err: {}", sessionId, ex.getMessage(), ex);
            throw ex;
        }
        // log saved content for debugging persistence issues (INFO so it appears in normal logs)
        try {
            String contentPreview = savedMessage.getContent() == null ? "null" :
                    (savedMessage.getContent().length() > 200 ? savedMessage.getContent().substring(0, 200) + "..." : savedMessage.getContent());
            int contentLength = savedMessage.getContent() == null ? 0 : savedMessage.getContent().length();
            log.info("Saved ChatMessage (addUserMessage) - sessionId: {}, messageId: {}, contentLength: {}, preview: {}",
                    sessionId, savedMessage.getId(), contentLength, contentPreview);
        } catch (Exception e) {
            log.debug("Unable to log saved ChatMessage content (addUserMessage): {}", e.getMessage());
        }
        // 原子性更新 ChatSession 的统计与最后消息（避免分步更新导致短期不一致）
        try {
            updateChatSessionStatsAtomic(sessionId, 1, 0, savedMessage.getId(), savedMessage.getCreateTime());
        } catch (Exception e) {
            log.warn("原子更新 ChatSession 统计失败（非致命）: {}", e.getMessage());
        }

        log.debug("添加用户消息，会话ID: {}, 消息ID: {}, 消息序号: {}", sessionId, savedMessage.getId(), messageIndex);
        // 更新用户 active session in Redis
        try {
            if (session.getSysUserId() != null) {
                String activeKey = "user:active-session:" + session.getSysUserId();
                redisTemplate.opsForValue().set(activeKey, sessionId.toString(), java.time.Duration.ofDays(7));
            }
        } catch (Exception e) {
            log.debug("更新 Redis active session 失败: {}", e.getMessage());
        }

        // 1) 缓存最近消息到 Redis 列表（保留最近 N 条）
        try {
            String recentKey = "session:recent:" + sessionId;
            // store as map/json to ensure cross-process readability (keep recent entries consistent)
            @SuppressWarnings("unchecked")
            Map<String, Object> asMap = objectMapper.convertValue(savedMessage, Map.class);
            redisTemplate.opsForList().leftPush(recentKey, asMap);
            redisTemplate.opsForList().trim(recentKey, 0, 49); // keep 50 items
            redisTemplate.expire(recentKey, java.time.Duration.ofDays(7));
        } catch (Exception e) {
            log.debug("写入 Redis 最近消息失败: {}", e.getMessage());
        }

        // 2) Update MySQL conversation_session (best-effort) using sessionId.
        try {
            conversationSessionRepository.findById(sessionId).ifPresent(conv -> {
                if (conv.getIsDeleted() != null && conv.getIsDeleted() == AIChatConstants.DELETED_TRUE) {
                    return;
                }
                Integer oldCount = conv.getMessageCount() == null ? 0 : conv.getMessageCount();
                conv.setMessageCount(oldCount + 1);
                conv.setLastMessageTime(java.time.LocalDateTime.now());
                conversationSessionRepository.save(conv);
            });
        } catch (Exception e) {
            log.warn("Update MySQL conversation_session failed (non-fatal): {}", e.getMessage());
        }

        return savedMessage;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateMessageAudioUrl(UUID messageId, String audioUrl) {
        if (messageId == null || audioUrl == null) return;
        try {
            Query q = new Query(Criteria.where(AIChatConstants.FIELD_ID).is(messageId));
            Update u = new Update().set("audio_url", audioUrl).set("update_time", LocalDateTime.now());
            mongoTemplate.updateFirst(q, u, ChatMessage.class);
        } catch (Exception e) {
            log.warn("updateMessageAudioUrl failed for messageId {}: {}", messageId, e.getMessage());
        }
    }

    @Override
    public ChatMessage saveAssistantMessage(UUID sessionId, String content, UUID parentMessageId) {
        // 获取会话信息（先尝试通过 service 懒创建以容忍 Mongo 延迟/创建竞态，再短重试）
        ChatSession session = chatSessionRepository.findById(sessionId).orElse(null);
        if (session == null) {
            // 尝试触发懒创建（如果 MySQL conversation_session 存在，service 会将其写入 Mongo）
            try {
                chatSessionService.getChatSessionById(sessionId);
            } catch (BusinessException be) {
                // 如果 service 明确表示会话不存在，则按原逻辑抛出
                throw be;
            } catch (Exception e) {
                log.debug("Attempt to auto-create ChatSession via service failed: {}", e.getMessage());
            }

            // 重新读取一次并做短重试
            session = chatSessionRepository.findById(sessionId).orElse(null);
            if (session == null) {
                final int maxAttempts = 3;
                final long sleepMillis = 200L;
                for (int attempt = 1; attempt <= maxAttempts && session == null; attempt++) {
                    try {
                        Thread.sleep(sleepMillis);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        break;
                    }
                    session = chatSessionRepository.findById(sessionId).orElse(null);
                    log.debug("Retry fetch ChatSession attempt {}/{} for sessionId {} -> {}", attempt, maxAttempts, sessionId, session != null);
                }
            }
        }
        if (session == null) {
            log.warn("ChatSession not found after lazy-create+retries, sessionId: {}", sessionId);
            throw new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage());
        }

        // 计算消息序号：当前会话的消息数量 + 1
        Long currentMessageCount = session.getMessageCount() != null ? session.getMessageCount() : 0L;
        Integer messageIndex = currentMessageCount.intValue() + 1;

        // 如果没有传入父消息ID，则尝试获取最后一条消息
        if (parentMessageId == null) {
            ChatMessage lastMessage = chatMessageRepository
                    .findFirstBySessionIdOrderByCreateTimeDesc(sessionId);
            if (lastMessage != null) {
                parentMessageId = lastMessage.getId();
            }
        }

        // 估算token数量
        Integer tokenCount = estimateTokens(content);

        // defensive: ensure content is not null or blank; if blank, store a placeholder to avoid empty messages
        String safeContent = content == null ? "" : content;
        if (safeContent.isBlank()) {
            safeContent = "[Audio Response]";
        }
        String safePreview = safeContent.length() > 200 ? safeContent.substring(0, 200) + "..." : safeContent;
        log.info("Preparing to save assistant message (saveAssistantMessage) - sessionId: {}, messageIndex: {}, preview: {}",
                sessionId, messageIndex, safePreview);

        ChatMessage message = new ChatMessage();
        // use UUID (time-ordered) for message ID
        message.setId(UuidCreator.getTimeOrdered());
        message.setSessionId(sessionId);
        message.setSysUserId(session.getSysUserId());
        message.setParentMessageId(parentMessageId);
        message.setMessageIndex(messageIndex);
        message.setRole(AIChatConstants.ROLE_ASSISTANT);
        message.setContent(safeContent);
        message.setMessageType(AIChatConstants.MESSAGE_TYPE_TEXT);
        message.setModelName(AIChatConstants.MODEL_QWEN3_MAX);
        message.setTokenCount(tokenCount);
        message.setIsFeedback(AIChatConstants.FEEDBACK_NONE);
        message.setIsDeleted(AIChatConstants.DELETED_FALSE);
        message.setCreateTime(LocalDateTime.now());
        message.setUpdateTime(LocalDateTime.now());

        ChatMessage savedMessage;
        // Debug: log assistant content before saving
        try {
            String dbgPreview = content == null ? "null" : (content.length() > 300 ? content.substring(0, 300) + "..." : content);
            log.debug("saveAssistantMessage - about to save assistant content (preview): {}", dbgPreview);
        } catch (Exception e) {
            log.debug("saveAssistantMessage - failed to log content preview: {}", e.getMessage());
        }
        try {
            log.info("Saving ChatMessage to Mongo (saveAssistantMessage), sessionId: {}, messageIndex: {}, role: {}",
                    sessionId, messageIndex, message.getRole());
            savedMessage = chatMessageRepository.save(message);
        } catch (Exception ex) {
            log.error("保存 ChatMessage 到 Mongo 失败 (saveAssistantMessage), sessionId: {}, err: {}", sessionId, ex.getMessage(), ex);
            throw ex;
        }
        // log saved content for debugging persistence issues (INFO so it appears in normal logs)
        try {
            String contentPreview = savedMessage.getContent() == null ? "null" :
                    (savedMessage.getContent().length() > 200 ? savedMessage.getContent().substring(0, 200) + "..." : savedMessage.getContent());
            int contentLength = savedMessage.getContent() == null ? 0 : savedMessage.getContent().length();
            log.info("Saved ChatMessage (saveAssistantMessage) - sessionId: {}, messageId: {}, contentLength: {}, preview: {}",
                    sessionId, savedMessage.getId(), contentLength, contentPreview);
        } catch (Exception e) {
            log.debug("Unable to log saved ChatMessage content (saveAssistantMessage): {}", e.getMessage());
        }
        // 原子性更新 ChatSession 的统计与最后消息（避免分步更新导致短期不一致）
        try {
            updateChatSessionStatsAtomic(sessionId, 1, tokenCount, savedMessage.getId(), savedMessage.getCreateTime());
        } catch (Exception e) {
            log.warn("原子更新 ChatSession 统计失败（非致命）: {}", e.getMessage());
        }

        log.debug("保存AI助手消息，会话ID: {}, 消息ID: {}, 消息序号: {}, Token数: {}", 
                sessionId, savedMessage.getId(), messageIndex, tokenCount);
        // 更新用户 active session in Redis
        try {
            if (session.getSysUserId() != null) {
                String activeKey = "user:active-session:" + session.getSysUserId();
                redisTemplate.opsForValue().set(activeKey, sessionId.toString(), java.time.Duration.ofDays(7));
            }
        } catch (Exception e) {
            log.debug("更新 Redis active session 失败: {}", e.getMessage());
        }

        // 1) 缓存最近消息到 Redis 列表（保留最近 N 条）
        try {
            String recentKey = "session:recent:" + sessionId;
            // normalize cached format to Map for consistent deserialization across services
            @SuppressWarnings("unchecked")
            Map<String, Object> asMap = objectMapper.convertValue(savedMessage, Map.class);
            redisTemplate.opsForList().leftPush(recentKey, asMap);
            redisTemplate.opsForList().trim(recentKey, 0, 49); // keep 50 items
            redisTemplate.expire(recentKey, java.time.Duration.ofDays(7));
        } catch (Exception e) {
            log.debug("写入 Redis 最近消息失败: {}", e.getMessage());
        }

        // 2) Update MySQL conversation_session (best-effort) using sessionId.
        try {
            conversationSessionRepository.findById(sessionId).ifPresent(conv -> {
                if (conv.getIsDeleted() != null && conv.getIsDeleted() == AIChatConstants.DELETED_TRUE) {
                    return;
                }
                Integer oldCount = conv.getMessageCount() == null ? 0 : conv.getMessageCount();
                conv.setMessageCount(oldCount + 1);
                conv.setLastMessageTime(java.time.LocalDateTime.now());
                conversationSessionRepository.save(conv);
            });
        } catch (Exception e) {
            log.warn("Update MySQL conversation_session failed (non-fatal): {}", e.getMessage());
        }

        return savedMessage;
    }

    /**
     * 更新会话的消息计数和token总数
     * 使用MongoDB的原子操作，确保数据一致性
     *
     * @param sessionId        会话ID
     * @param messageIncrement 消息数量增量
     * @param tokenIncrement   token数量增量
     */
    @SuppressWarnings("unused")
    private void updateSessionMessageCount(UUID sessionId, int messageIncrement, int tokenIncrement) {
        Query query = new Query(Criteria.where(AIChatConstants.FIELD_ID).is(sessionId));
        Update update = new Update();

        // 原子性增加消息计数
        if (messageIncrement > 0) {
            update.inc(AIChatConstants.FIELD_MESSAGE_COUNT, messageIncrement);
        }

        // 原子性增加token总数
        if (tokenIncrement > 0) {
            update.inc(AIChatConstants.FIELD_TOTAL_TOKENS, tokenIncrement);
        }

        // 更新最后消息时间
        update.set(AIChatConstants.FIELD_UPDATE_TIME, LocalDateTime.now());

        mongoTemplate.updateFirst(query, update, ChatSession.class);
    }

    // Note: kept for backward compatibility; primary callers now use updateChatSessionStatsAtomic

    private Integer estimateTokens(String text) {
        return (int) (text.length() * AIChatConstants.TOKEN_ESTIMATE_RATIO);
    }

    /**
     * 原子性更新 ChatSession 的统计信息：message_count、total_tokens、last_message_id、last_message_time、update_time
     */
    private void updateChatSessionStatsAtomic(UUID chatSessionId, int messageIncrement, int tokenIncrement, UUID lastMessageId, LocalDateTime lastMessageTime) {
        try {
            Query query = new Query(Criteria.where(AIChatConstants.FIELD_ID).is(chatSessionId));
            Update update = new Update();
            if (messageIncrement > 0) update.inc(AIChatConstants.FIELD_MESSAGE_COUNT, messageIncrement);
            if (tokenIncrement > 0) update.inc(AIChatConstants.FIELD_TOTAL_TOKENS, tokenIncrement);
            if (lastMessageId != null) update.set(AIChatConstants.FIELD_LAST_MESSAGE_ID, lastMessageId);
            if (lastMessageTime != null) update.set(AIChatConstants.FIELD_LAST_MESSAGE_TIME, lastMessageTime);
            update.set(AIChatConstants.FIELD_UPDATE_TIME, LocalDateTime.now());
            // findAndModify to return the modified document if needed (not used here)
            mongoTemplate.findAndModify(query, update, org.springframework.data.mongodb.core.FindAndModifyOptions.options().returnNew(false), com.echoes.conversation.domain.chat.entity.po.ChatSession.class);
        } catch (Exception e) {
            log.debug("updateChatSessionStatsAtomic failed: {}", e.getMessage());
            throw e;
        }
    }
}

