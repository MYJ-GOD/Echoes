package com.echoes.conversation.domain.chat.service.impl;

import com.echoes.conversation.common.constants.AIChatConstants;
import com.echoes.conversation.domain.chat.entity.dto.ChatSessionQueryDTO;
import com.echoes.conversation.domain.chat.entity.po.ChatMessage;
import com.echoes.conversation.domain.chat.entity.po.ChatSession;
import com.echoes.conversation.domain.chat.entity.po.ConversationSession;
import com.echoes.conversation.domain.chat.entity.vo.ChatSessionVO;
import com.echoes.conversation.domain.chat.enums.AIChatEnum;
import com.echoes.conversation.domain.chat.enums.SessionStatus;
import com.echoes.conversation.domain.chat.enums.SessionTypeEnum;
import com.echoes.exception.BusinessException;
import com.echoes.conversation.domain.chat.repository.ChatMessageRepository;
import com.echoes.conversation.domain.chat.repository.ChatSessionRepository;
import com.echoes.conversation.domain.chat.repository.ConversationSessionRepository;
import com.echoes.conversation.domain.chat.service.IChatSessionService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.f4b6a3.uuid.UuidCreator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatSessionServiceImpl implements IChatSessionService {

    private final ChatSessionRepository chatSessionRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final ConversationSessionRepository conversationSessionRepository;
    private final MongoTemplate mongoTemplate;
    private final RedisTemplate<String, Object> redisTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    @Transactional(readOnly = true)
    public List<ChatSessionVO> listChatSession(ChatSessionQueryDTO chatSessionQueryDTO) {
        if (chatSessionQueryDTO == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        Query query = new Query();
        Criteria criteria = new Criteria();

        if (chatSessionQueryDTO.getSysUserId() != null) {
            // 前端会以 string 形式传递 sysUserId（UUID 字符串），Mongo 中存的是 UUID 类型
            // 需要尝试将其解析为 UUID 再进行查询，避免类型不匹配导致查询为空
            try {
                UUID uid = com.echoes.utils.UuidUtils.parseLenient(chatSessionQueryDTO.getSysUserId());
                if (uid != null) {
                    criteria.and(AIChatConstants.FIELD_SYS_USER_ID).is(uid);
                } else {
                    // 解析失败时退化为按原始字符串查询（兼容历史数据/调用）
                    criteria.and(AIChatConstants.FIELD_SYS_USER_ID).is(chatSessionQueryDTO.getSysUserId());
                }
            } catch (Exception e) {
                // 解析失败时退化为按原始字符串查询（兼容历史数据/调用）
                criteria.and(AIChatConstants.FIELD_SYS_USER_ID).is(chatSessionQueryDTO.getSysUserId());
            }
        }

        if (StringUtils.hasText(chatSessionQueryDTO.getSessionTitle())) {
            criteria.and(AIChatConstants.FIELD_SESSION_TITLE).regex(chatSessionQueryDTO.getSessionTitle(), "i");
        }
        query.addCriteria(criteria);
        query.with(Sort.by(
                Sort.Order.desc(AIChatConstants.FIELD_IS_PINNED),
                Sort.Order.desc(AIChatConstants.FIELD_UPDATE_TIME)
        ));

        Pageable pageable = PageRequest.of(
                chatSessionQueryDTO.getPageNum() - AIChatConstants.PAGE_NUM_OFFSET,
                chatSessionQueryDTO.getPageSize()
        );

        query.with(pageable);

        List<ChatSession> sessions = mongoTemplate.find(query, ChatSession.class);
        return batchConvertToVO(sessions);
    }

    @Override
    @Transactional(readOnly = true)
    public List<ChatSessionVO> listAllChatSessionByUserId(java.util.UUID sysUserId) {
        if (sysUserId == null) {
            throw new BusinessException(AIChatEnum.SESSION_USER_ID_REQUIRED.getCode(), AIChatEnum.SESSION_USER_ID_REQUIRED.getMessage());
        }

        Query query = new Query();
        query.addCriteria(Criteria.where(AIChatConstants.FIELD_SYS_USER_ID).is(sysUserId));
        query.with(Sort.by(
                Sort.Order.desc(AIChatConstants.FIELD_IS_PINNED),
                Sort.Order.desc(AIChatConstants.FIELD_UPDATE_TIME)
        ));

        List<ChatSession> sessions = mongoTemplate.find(query, ChatSession.class);
        return batchConvertToVO(sessions);
    }

    @Override
    @Transactional(readOnly = true)
    public ChatSessionVO getChatSessionById(UUID id) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        ChatSession session = chatSessionRepository.findById(id).orElse(null);
        if (session == null) {
            ConversationSession conv = conversationSessionRepository.findById(id).orElse(null);
            if (conv != null && (conv.getIsDeleted() == null || conv.getIsDeleted() == 0)) {
                ChatSession created = new ChatSession();
                created.setId(conv.getConversationId());
                created.setSysUserId(conv.getUserId());
                created.setVoiceId(conv.getDefaultVoiceAssetId());
                created.setSessionTitle(conv.getSessionTitle());
                created.setSessionType(SessionTypeEnum.GENERAL.getCode());
                created.setModelName(AIChatConstants.MODEL_QWEN3_MAX);
                created.setIsPinned(AIChatConstants.PINNED_FALSE);
                created.setIsFavorite(AIChatConstants.FAVORITE_FALSE);
                created.setIsArchived(AIChatConstants.ARCHIVED_FALSE);
                created.setMessageCount(0L);
                created.setTotalTokens(0L);
                created.setCreateTime(LocalDateTime.now());
                created.setUpdateTime(LocalDateTime.now());
                session = chatSessionRepository.save(created);
            }
        }
        if (session == null) {
            throw new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage());
        }

        return convertToVO(session);
    }

    /**
     * 创建新会话
     * 初始化会话的所有字段，包括新增的统计字段
     *
     * @param courseId 课程ID（可选）
     * @param sessionType 会话类型（可选，默认为普通对话）
     * @param title 会话标题（可选，默认为"新对话"）
     * @return 创建的会话VO
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public ChatSessionVO addChatSession(UUID courseId, Integer sessionType, String title, java.util.UUID sysUserId) {
        // 1. Ensure MySQL conversation_session exists (avoid creating duplicates if caller already created it)
        ConversationSession savedConversation = null;
        if (sysUserId != null && StringUtils.hasText(title)) {
            try {
                var opt = conversationSessionRepository.findFirstByUserIdAndSessionTitleAndIsDeletedOrderByLastMessageTimeDesc(
                        sysUserId, title, 0);
                if (opt != null && opt.isPresent()) {
                    savedConversation = opt.get();
                }
            } catch (Exception e) {
                log.debug("Error checking existing ConversationSession: {}", e.getMessage());
            }
        }

        if (savedConversation == null && sysUserId != null) {
            ConversationSession conversationSession = new ConversationSession();
            // assign UUID primary key before persisting (BINARY(16) PK)
            conversationSession.setConversationId(java.util.UUID.randomUUID());
            conversationSession.setUserId(sysUserId);
            conversationSession.setDefaultVoiceAssetId(null);
            conversationSession.setSessionTitle(StringUtils.hasText(title) ? title : AIChatConstants.DEFAULT_SESSION_TITLE);
            // v3 schema: only set authoritative index fields
            conversationSession.setStatus(SessionStatus.ACTIVE);
            conversationSession.setLastMessageTime(null);
            conversationSession.setMessageCount(0);
            conversationSession.setDefaults(buildDefaultsJson(null, false, true, "chat_session_service"));
            conversationSession.setIsDeleted(AIChatConstants.DELETED_FALSE);
            conversationSession.setCreateTime(LocalDateTime.now());
            conversationSession.setUpdateTime(LocalDateTime.now());
            savedConversation = conversationSessionRepository.save(conversationSession);
        }

        // 2. ???? conversation_session????? ID ? ChatSession
        if (savedConversation != null) {
            java.util.UUID convId = savedConversation.getConversationId();
            if (convId != null) {
                var opt = chatSessionRepository.findById(convId);
                if (opt != null && opt.isPresent()) {
                    return convertToVO(opt.get());
                }
            }
        }

        ChatSession session = new ChatSession();
        // use UUID (time-ordered) for Mongo ID instead of epoch long
        if (savedConversation != null && savedConversation.getConversationId() != null) {
            session.setId(savedConversation.getConversationId());
        } else {
            session.setId(UuidCreator.getTimeOrdered());
        }
        session.setSysUserId(sysUserId);
        session.setSessionTitle(savedConversation != null ? savedConversation.getSessionTitle() : AIChatConstants.DEFAULT_SESSION_TITLE);
        session.setSessionType(sessionType != null ? sessionType : SessionTypeEnum.GENERAL.getCode());
        session.setModelName(AIChatConstants.MODEL_QWEN3_MAX);
        session.setIsPinned(AIChatConstants.PINNED_FALSE);
        session.setIsFavorite(AIChatConstants.FAVORITE_FALSE);
        session.setIsArchived(AIChatConstants.ARCHIVED_FALSE);
        session.setMessageCount(0L);
        session.setTotalTokens(0L);
        session.setCreateTime(LocalDateTime.now());
        session.setUpdateTime(LocalDateTime.now());

        ChatSession savedSession = chatSessionRepository.save(session);
        log.info("创建新会话，MySQL 会话ID: {}, Mongo 会话ID: {}, 标题: {}", 
                savedConversation != null ? savedConversation.getConversationId() : null,
                savedSession.getId(), savedSession.getSessionTitle());
        // write active session to Redis for quick restore
        try {
            if (sysUserId != null && savedSession.getId() != null) {
                String activeKey = "user:active-session:" + sysUserId;
                redisTemplate.opsForValue().set(activeKey, savedSession.getId().toString(), java.time.Duration.ofDays(7));
            }
        } catch (Exception e) {
            log.warn("写入 Redis 活跃会话失败: {}", e.getMessage());
        }
        return convertToVO(savedSession);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean updateChatSessionTitle(UUID id, String title) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        if (!StringUtils.hasText(title)) {
            throw new BusinessException(AIChatEnum.MESSAGE_CONTENT_REQUIRED.getCode(), AIChatEnum.MESSAGE_CONTENT_REQUIRED.getMessage());
        }

        ChatSession session = chatSessionRepository.findById(id)
                .orElseThrow(() -> new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage()));

        session.setSessionTitle(title);
        session.setUpdateTime(LocalDateTime.now());
        chatSessionRepository.save(session);

        conversationSessionRepository.findById(id).ifPresent(conv -> {
            if (conv.getIsDeleted() != null && conv.getIsDeleted() == AIChatConstants.DELETED_TRUE) {
                return;
            }
            conv.setSessionTitle(title);
            conv.setUpdateTime(LocalDateTime.now());
            conversationSessionRepository.save(conv);
        });

        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean removeChatSessionById(UUID id) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }
        try {
            chatMessageRepository.deleteBySessionId(id);
        } catch (Exception e) {
            log.warn("删除会话消息失败: {}", e.getMessage());
        }
        try {
            chatSessionRepository.deleteById(id);
        } catch (Exception e) {
            log.warn("删除 Mongo ChatSession 失败: {}", e.getMessage());
        }
        try {
            conversationSessionRepository.findById(id).ifPresent(conv -> {
                conv.setIsDeleted(AIChatConstants.DELETED_TRUE);
                conv.setDeletedAt(LocalDateTime.now());
                conv.setUpdateTime(LocalDateTime.now());
                conversationSessionRepository.save(conv);
            });
        } catch (Exception e) {
            log.warn("软删除 MySQL ConversationSession 失败: {}", e.getMessage());
        }
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Integer removeChatSessionByIds(List<UUID> ids) {
        if (ids == null || ids.isEmpty()) {
            return 0;
        }
        int deleted = 0;
        for (UUID id : ids) {
            if (id == null) {
                continue;
            }
            try {
                chatMessageRepository.deleteBySessionId(id);
            } catch (Exception e) {
                log.warn("批量删除会话消息失败: {}", e.getMessage());
            }
            try {
                chatSessionRepository.deleteById(id);
            } catch (Exception e) {
                log.warn("批量删除 Mongo ChatSession 失败: {}", e.getMessage());
            }
            try {
                conversationSessionRepository.findById(id).ifPresent(conv -> {
                    conv.setIsDeleted(AIChatConstants.DELETED_TRUE);
                    conv.setDeletedAt(LocalDateTime.now());
                    conv.setUpdateTime(LocalDateTime.now());
                    conversationSessionRepository.save(conv);
                });
            } catch (Exception e) {
                log.warn("软删除 MySQL ConversationSession 失败: {}", e.getMessage());
            }
            deleted++;
        }
        return deleted;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean pinSession(UUID id, Boolean isPinned) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        ChatSession session = chatSessionRepository.findById(id)
                .orElseThrow(() -> new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage()));

        session.setIsPinned(Boolean.TRUE.equals(isPinned) ?
                AIChatConstants.PINNED_TRUE : AIChatConstants.PINNED_FALSE);
        chatSessionRepository.save(session);

        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean favoriteSession(UUID id, Boolean isFavorite) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        ChatSession session = chatSessionRepository.findById(id)
                .orElseThrow(() -> new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage()));

        session.setIsFavorite(Boolean.TRUE.equals(isFavorite) ?
                AIChatConstants.FAVORITE_TRUE : AIChatConstants.FAVORITE_FALSE);
        chatSessionRepository.save(session);

        return true;
    }

    /**
     * 归档会话
     * 将会话标记为已归档状态
     *
     * @param id 会话ID
     * @return 是否成功
     * @throws BusinessException 当会话ID为空或会话不存在时抛出
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean archiveSession(UUID id) {
        if (id == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        ChatSession session = chatSessionRepository.findById(id)
                .orElseThrow(() -> new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage()));

        session.setIsArchived(AIChatConstants.ARCHIVED_TRUE);
        session.setUpdateTime(LocalDateTime.now());
        chatSessionRepository.save(session);

        log.info("会话已归档，会话ID: {}", id);
        return true;
    }

    /**
     * 更新会话的最后一条消息
     * 更新会话标题（如果为默认标题）、最后消息ID和时间
     *
     * @param sessionId 会话ID
     * @param lastMessage 最后一条消息内容
     * @return 是否成功
     * @throws BusinessException 当会话ID为空或会话不存在时抛出
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Boolean updateSessionLastMessage(UUID sessionId, String lastMessage) {
        if (sessionId == null) {
            throw new BusinessException(AIChatEnum.SESSION_ID_REQUIRED.getCode(), AIChatEnum.SESSION_ID_REQUIRED.getMessage());
        }

        ChatSession session = chatSessionRepository.findById(sessionId)
                .orElseThrow(() -> new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), AIChatEnum.SESSION_NOT_EXISTS.getMessage()));

        // 如果会话标题为默认标题，则使用最后一条消息作为标题
        if (AIChatConstants.DEFAULT_SESSION_TITLE.equals(session.getSessionTitle()) &&
                StringUtils.hasText(lastMessage)) {
            String title = lastMessage.length() > AIChatConstants.DEFAULT_TITLE_MAX_LENGTH ?
                    lastMessage.substring(AIChatConstants.DEFAULT_MESSAGE_COUNT,
                            AIChatConstants.DEFAULT_TITLE_MAX_LENGTH) + AIChatConstants.ELLIPSIS
                    : lastMessage;
            session.setSessionTitle(title);
        }

        // 获取最后一条消息ID和时间
        ChatMessage lastMessageEntity = chatMessageRepository
                .findFirstBySessionIdOrderByCreateTimeDesc(sessionId);
        if (lastMessageEntity != null) {
            session.setLastMessageId(lastMessageEntity.getId());
            session.setLastMessageTime(lastMessageEntity.getCreateTime());
        }

        session.setUpdateTime(LocalDateTime.now());
        chatSessionRepository.save(session);

        return true;
    }

    /**
     * 批量转换会话实体为VO
     * 优化：直接使用会话的messageCount字段，避免聚合查询
     * 使用lastMessageId获取最后一条消息，提升性能
     *
     * @param sessions 会话实体列表
     * @return 会话VO列表
     */
    private List<ChatSessionVO> batchConvertToVO(List<ChatSession> sessions) {
        if (sessions == null || sessions.isEmpty()) {
            return new ArrayList<>();
        }

        // 收集所有会话的最后消息ID
        List<UUID> lastMessageIds = sessions.stream()
                .map(ChatSession::getLastMessageId)
                .filter(java.util.Objects::nonNull)
                .distinct()
                .collect(Collectors.toList());

        // 批量查询最后一条消息（仅查询有lastMessageId的会话）
        Map<UUID, ChatMessage> lastMessageMap = new HashMap<>();
        if (!lastMessageIds.isEmpty()) {
            Query lastMessageQuery = new Query();
            lastMessageQuery.addCriteria(Criteria.where(AIChatConstants.FIELD_ID).in(lastMessageIds));
            List<ChatMessage> lastMessages = mongoTemplate.find(lastMessageQuery, ChatMessage.class);
            lastMessages.forEach(msg -> lastMessageMap.put(msg.getId(), msg));
        }

        // 对于没有lastMessageId的会话，通过sessionId查询最后一条消息
        List<UUID> sessionsWithoutLastMessageId = sessions.stream()
                .filter(s -> s.getLastMessageId() == null)
                .map(ChatSession::getId)
                .collect(Collectors.toList());

        if (!sessionsWithoutLastMessageId.isEmpty()) {
            for (UUID sessionId : sessionsWithoutLastMessageId) {
                ChatMessage lastMessage = chatMessageRepository
                        .findFirstBySessionIdOrderByCreateTimeDesc(sessionId);
                if (lastMessage != null) {
                    lastMessageMap.put(sessionId, lastMessage);
                }
            }
        }

        // 转换为VO，直接使用messageCount字段
        return sessions.stream()
                .map(session -> {
                    ChatSessionVO vo = new ChatSessionVO();
                    BeanUtils.copyProperties(session, vo);
                    // ensure id string is set (VO uses String)
                    vo.setId(session.getId() != null ? session.getId().toString() : null);

                    // 设置消息数量，直接使用会话的messageCount字段
                    Long messageCount = session.getMessageCount();
                    vo.setMessageCount(messageCount != null ? messageCount.intValue() : AIChatConstants.DEFAULT_MESSAGE_COUNT);

                    // 设置最后一条消息预览
                    ChatMessage lastMessage = null;
                    if (session.getLastMessageId() != null) {
                        lastMessage = lastMessageMap.get(session.getLastMessageId());
                    } else {
                        lastMessage = lastMessageMap.get(session.getId());
                    }

                    if (lastMessage != null) {
                        String preview = lastMessage.getContent();
                        if (preview != null && preview.length() > AIChatConstants.DEFAULT_PREVIEW_MAX_LENGTH) {
                            preview = preview.substring(0, AIChatConstants.DEFAULT_PREVIEW_MAX_LENGTH) + AIChatConstants.ELLIPSIS;
                        }
                        vo.setLastMessagePreview(preview);
                    }

                    return vo;
                })
                .collect(Collectors.toList());
    }

    /**
     * 转换单个会话实体为VO
     * 优化：直接使用会话的messageCount字段和lastMessageId，避免查询
     *
     * @param session 会话实体
     * @return 会话VO
     */
    private ChatSessionVO convertToVO(ChatSession session) {
        ChatSessionVO vo = new ChatSessionVO();
        BeanUtils.copyProperties(session, vo);
        // ensure id string is set (VO uses String)
        vo.setId(session.getId() != null ? session.getId().toString() : null);

        // 直接使用会话的messageCount字段
        Long messageCount = session.getMessageCount();
        vo.setMessageCount(messageCount != null ? messageCount.intValue() : AIChatConstants.DEFAULT_MESSAGE_COUNT);

        // 优先使用lastMessageId获取最后一条消息
        ChatMessage lastMessage = null;
        if (session.getLastMessageId() != null) {
            lastMessage = chatMessageRepository.findById(session.getLastMessageId()).orElse(null);
        }

        // 如果没有lastMessageId或查询失败，则通过sessionId查询
        if (lastMessage == null) {
            lastMessage = chatMessageRepository
                    .findFirstBySessionIdOrderByCreateTimeDesc(session.getId());
        }

        if (lastMessage != null) {
            String preview = lastMessage.getContent();
            if (preview != null && preview.length() > AIChatConstants.DEFAULT_PREVIEW_MAX_LENGTH) {
                preview = preview.substring(0, AIChatConstants.DEFAULT_PREVIEW_MAX_LENGTH) + AIChatConstants.ELLIPSIS;
            }
            vo.setLastMessagePreview(preview);
        }

        return vo;
    }

    private String buildDefaultsJson(UUID voiceAssetId, boolean strictVoice, boolean streamMode, String source) {
        Map<String, Object> defaults = new LinkedHashMap<>();
        defaults.put("selectedVoiceAssetId", voiceAssetId != null ? voiceAssetId.toString() : null);
        defaults.put("strictVoice", strictVoice);
        defaults.put("streamMode", streamMode);
        defaults.put("source", source);
        defaults.put("updatedAt", LocalDateTime.now().toString());
        try {
            return objectMapper.writeValueAsString(defaults);
        } catch (Exception e) {
            return "{\"strictVoice\":false,\"streamMode\":true}";
        }
    }
}

