package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.domain.chat.entity.po.ConversationSession;
import com.echoes.conversation.domain.chat.entity.vo.ConversationSessionVO;
import com.echoes.conversation.domain.chat.repository.ConversationSessionRepository;
import com.echoes.conversation.domain.chat.service.IChatMessageService;
import com.echoes.conversation.domain.chat.service.IChatSessionService;
import com.echoes.conversation.common.result.Result;
import com.echoes.conversation.config.JwtProperties;
import com.echoes.conversation.common.constants.AIChatConstants;
import com.echoes.conversation.common.constants.JwtClaimsConstant;
import com.echoes.conversation.common.result.PageResult;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.validation.annotation.Validated;
import org.springframework.beans.BeanUtils;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;
import com.echoes.utils.UuidUtils;

/**
 * 基于 MySQL conversation_session 的联系人会话接口
 * 仅负责联系人索引的增删改查，不涉及具体聊天记录
 */
@Tag(name = "联系人会话（MySQL）", description = "基于 conversation_session 表的联系人管理接口")
@RestController
@RequestMapping("/conversation-session")
@RequiredArgsConstructor
@Slf4j
@Validated
public class ConversationSessionController {

    private final ConversationSessionRepository conversationSessionRepository;
    private final IChatMessageService chatMessageService;
    private final IChatSessionService chatSessionService;
    private final JwtProperties jwtProperties;
    private final ObjectMapper objectMapper;
    private static final String DEFAULT_SESSION_TITLE = "新的对话";

    /**
     * 创建联系人会话（仅写入 MySQL，会话索引表）
     *
     * @param title            会话标题（可选）
     * @param voiceId          声纹模型 ID（可选）
     * @param userIdParam      前端传入的用户 ID（备用）
     * @param userIdHeader     网关透传的 X-USER-ID（优先）
     * @param authorization    Authorization 头（Bearer token 回退解析用户 ID）
     * @return 创建后的 ConversationSessionVO 包装在 Result 中，失败返回标准错误码
     */
    @PostMapping
    public Result<ConversationSessionVO> createSession(
            @Parameter(name = "title", description = "会话标题")
            @RequestParam(value = "title", required = false) String title,
            @Parameter(name = "voiceId", description = "声纹模型 ID")
            @RequestParam(value = "voiceId", required = false) String voiceId,
            @Parameter(name = "userId", description = "用户 ID（已废弃，仅作兼容保留；实际取网关注入的 X-USER-ID）")
            @RequestParam(value = "userId", required = false) String userIdParam,
            @RequestHeader(value = "X-USER-ID", required = false) String userIdHeader
            , @RequestHeader(value = "Authorization", required = false) String authorization
    ) {
        log.info("createSession called: title='{}', userIdHeader='{}', userIdParamPresent={}, authorizationPresent={}",
                title, userIdHeader, userIdParam != null && !userIdParam.isBlank(), authorization != null && !authorization.isBlank());

        // 一律从 BaseContext 获取用户 ID（UserContextFilter 已从网关注入的 X-USER-ID 设置）
        java.util.UUID userId = com.echoes.context.BaseContext.getCurrentId();

        // Fallback：网关未注入 X-USER-ID 时（开发环境/旧客户端），尝试从 Authorization token 解析
        if (userId == null && authorization != null && authorization.startsWith("Bearer ")) {
            try {
                String token = authorization.substring(7);
                var decoded = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
                String uid = decoded.getClaim(JwtClaimsConstant.USER_ID).asString();
                if (uid != null && !uid.isBlank()) {
                    userId = UuidUtils.parseLenient(uid);
                }
            } catch (Exception e) {
                log.warn("Failed to parse userId from Authorization token: {}", e.getMessage());
            }
        }

        if (userId == null) {
            log.error("createSession rejected: userId is null after all resolution attempts");
            return Result.error("用户未登录或认证信息缺失");
        }

        String userIdStr = userId.toString();

        log.debug("Resolved userId: {}", userId);

        ConversationSession session = new ConversationSession();
        session.setUserId(userId);
        try {
            if (voiceId != null && !voiceId.isBlank()) {
                java.util.UUID parsed = UuidUtils.parseLenient(voiceId);
                session.setDefaultVoiceAssetId(parsed);
            }
        } catch (Exception e) {
            log.debug("Failed to parse voiceId '{}': {}", voiceId, e.getMessage(), e);
        }
        session.setSessionTitle((title != null && !title.isBlank()) ? title : DEFAULT_SESSION_TITLE);
        // New schema v3: only set stable, authoritative fields
        session.setStatus(com.echoes.conversation.domain.chat.enums.SessionStatus.ACTIVE);
        session.setLastMessageTime(null);
        session.setMessageCount(0);
        session.setDefaults(buildDefaultsJson(session.getDefaultVoiceAssetId(), false, true, "create_session"));
        auditDefaultsInitialized(session, "create_session");
        session.setIsDeleted(AIChatConstants.DELETED_FALSE);
        session.setCreateTime(LocalDateTime.now());
        session.setUpdateTime(LocalDateTime.now());

        // ensure conversation_id UUID is set if not provided
        if (session.getConversationId() == null) {
            session.setConversationId(java.util.UUID.randomUUID());
        }
        ConversationSession saved;
        try {
            saved = conversationSessionRepository.save(session);
        } catch (Exception e) {
            log.error("Failed to save ConversationSession to MySQL (userId={}, title={})", userId, session.getSessionTitle(), e);
            return Result.error("DB_SAVE_FAILED: " + (e.getMessage() != null ? e.getMessage() : "unknown"));
        }

        // Best-effort: ensure Mongo ChatSession and Redis active-session exist to avoid "session not exists" on immediate use.
        try {
            if (saved != null && saved.getUserId() != null) {
                chatSessionService.addChatSession(null, null, saved.getSessionTitle(), saved.getUserId());
            }
        } catch (Exception e) {
            log.warn("Post-create: ensure Mongo ChatSession / Redis active key failed for conversationId {}: {}",
                    saved != null ? saved.getConversationId() : null, e.getMessage());
        }

        com.echoes.conversation.domain.chat.entity.vo.ConversationSessionVO vo = toVO(saved);
        return Result.success(vo);
    }

    @RequestMapping("/ping")
    public Result<String> ping() {
        /**
         * 健康检查接口，用于路由调试和连通性测试。
         *
         * @return "pong" 表示服务正常
         */
        log.info("ping endpoint called on ConversationSessionController");
        return Result.success("pong");
    }

    /**
     * 列出指定用户的 ConversationSession 列表
     * @param userId 用户 UUID 字符串
     * @return ConversationSessionVO 列表封装在 Result 中
     */
    @GetMapping("/user/{userId}")
    public Result<List<ConversationSessionVO>> listByUserId(
            @Parameter(name = "userId", description = "用户 ID", required = true)
            @PathVariable("userId") String userId
    ) {
        java.util.UUID uid = null;
        try {
            uid = UuidUtils.parseLenient(userId);
        } catch (Exception e) {
            log.debug("Failed to parse userId '{}' in listByUserId: {}", userId, e.getMessage(), e);
            return Result.error("INVALID_USER_ID");
        }

        if (uid == null) {
            log.warn("listByUserId called with null userId (raw='{}')", userId);
            return Result.error("USER_ID_REQUIRED");
        }

        try {
            List<ConversationSession> sessions = conversationSessionRepository
                    .findByUserIdAndIsDeletedOrderByLastMessageTimeDesc(uid, 0);
            List<ConversationSessionVO> voList = sessions.stream().map(this::toVO).collect(Collectors.toList());
            return Result.success(voList);
        } catch (Exception e) {
            log.error("Failed to list sessions for user {}: {}", uid, e.getMessage(), e);
            return Result.error("SERVER_ERROR");
        }
    }

    /**
     * 分页查询指定用户的 ConversationSession 列表
     * @param userId 用户 UUID 字符串
     * @param page 页码（从 1 开始）
     * @param size 每页数量
     * @return 分页结果封装在 Result 中
     */
    @GetMapping("/user/{userId}/page")
    public Result<PageResult<ConversationSessionVO>> listByUserIdPaged(
            @Parameter(name = "userId", description = "用户 ID", required = true)
            @PathVariable("userId") String userId,
            @Parameter(name = "page", description = "页码（从 1 开始）", required = false)
            @RequestParam(value = "page", defaultValue = "1") Integer page,
            @Parameter(name = "size", description = "每页数量", required = false)
            @RequestParam(value = "size", defaultValue = "20") Integer size
    ) {
        java.util.UUID uid = null;
        try {
            uid = UuidUtils.parseLenient(userId);
        } catch (Exception e) {
            log.debug("Failed to parse userId '{}' in listByUserIdPaged: {}", userId, e.getMessage(), e);
            return Result.error("INVALID_USER_ID");
        }

        if (uid == null) {
            log.warn("listByUserIdPaged called with null userId (raw='{}')", userId);
            return Result.error("USER_ID_REQUIRED");
        }

        // 限制每页最大数量
        if (size > 100) {
            size = 100;
        }

        try {
            PageRequest pageRequest = PageRequest.of(page - 1, size, Sort.by(Sort.Direction.DESC, "lastMessageTime"));
            Page<ConversationSession> sessionPage = conversationSessionRepository.findByUserIdAndIsDeleted(uid, 0, pageRequest);

            List<ConversationSessionVO> voList = sessionPage.getContent().stream().map(this::toVO).collect(Collectors.toList());
            PageResult<ConversationSessionVO> pageResult = new PageResult<>(
                    voList,
                    sessionPage.getTotalElements(),
                    (long) sessionPage.getNumber() + 1,
                    (long) sessionPage.getSize()
            );
            return Result.success(pageResult);
        } catch (Exception e) {
            log.error("Failed to list paged sessions for user {}: {}", uid, e.getMessage(), e);
            return Result.error("SERVER_ERROR");
        }
    }

    /**
     * 获取会话消息历史
     */
    @GetMapping("/{conversationId}/messages")
    public Result<List<com.echoes.conversation.domain.chat.entity.po.ChatMessage>> getSessionMessages(
            @Parameter(name = "conversationId", description = "会话 ID", required = true)
            @PathVariable("conversationId") String conversationId,
            @Parameter(name = "limit", description = "返回消息数量", required = false)
            @RequestParam(value = "limit", defaultValue = "50") Integer limit
    ) {
        java.util.UUID cid = UuidUtils.parseLenient(conversationId);
        if (cid == null) {
            return Result.error("无效的会话 ID");
        }
        try {
            List<com.echoes.conversation.domain.chat.entity.po.ChatMessage> messages = chatMessageService.listMessagesBySessionId(cid, limit);
            return Result.success(messages);
        } catch (Exception e) {
            log.error("加载历史消息失败，conversationId: {}, err: {}", cid, e.getMessage(), e);
            return Result.error("服务器错误");
        }
    }

    @PutMapping("/{conversationId}/title")
    public Result<Boolean> updateTitle(
            @Parameter(name = "conversationId", description = "会话 ID", required = true)
            @PathVariable("conversationId") String conversationId,
            @Parameter(name = "title", description = "新标题", required = true)
            @RequestParam("title") String title
    ) {
        /**
         * 更新会话标题
         * @param conversationId 会话 UUID 字符串
         * @param title 新标题
         * @return 操作是否成功
         */
        java.util.UUID cid = UuidUtils.parseLenient(conversationId);
        ConversationSession session = conversationSessionRepository.findById(cid)
                .orElse(null);
        if (session == null) {
            return Result.success(false);
        }
        if (session.getIsDeleted() != null && session.getIsDeleted() == AIChatConstants.DELETED_TRUE) {
            return Result.success(false);
        }
        session.setSessionTitle(title);
        session.setUpdateTime(LocalDateTime.now());
        conversationSessionRepository.save(session);
        return Result.success(true);
    }

    /**
     * 更新联系人的声纹模型 ID
     * 用于将音色与联系人关联
     *
     * @param conversationId 会话 ID
     * @param voiceId        声纹模型 ID
     * @return 操作是否成功
     */
    @PutMapping("/{conversationId}/voiceId")
    public Result<Boolean> updateVoiceId(
            @Parameter(name = "conversationId", description = "会话 ID", required = true)
            @PathVariable("conversationId") String conversationId,
            @Parameter(name = "voiceId", description = "声纹模型 ID", required = true)
            @RequestParam("voiceId") String voiceId
    ) {
        /**
         * 更新会话的 voiceId（声纹模型 ID）
         * @param conversationId 会话 UUID 字符串
         * @param voiceId 声纹模型 ID 字符串
         * @return 操作是否成功
         */
        java.util.UUID cid = UuidUtils.parseLenient(conversationId);
        ConversationSession session = conversationSessionRepository.findById(cid)
                .orElse(null);
        if (session == null) {
            return Result.success(false);
        }
        if (session.getIsDeleted() != null && session.getIsDeleted() == AIChatConstants.DELETED_TRUE) {
            return Result.success(false);
        }
        java.util.UUID parsedVoiceId;
        try {
            parsedVoiceId = UuidUtils.parseLenient(voiceId);
        } catch (Exception e) {
            log.debug("Failed to parse voiceId '{}' when updating voiceId: {}", voiceId, e.getMessage(), e);
            return Result.error("INVALID_VOICE_ID");
        }
        if (parsedVoiceId == null) {
            return Result.error("INVALID_VOICE_ID");
        }
        String oldDefaults = session.getDefaults();
        java.util.UUID oldVoiceAssetId = session.getDefaultVoiceAssetId();
        session.setDefaultVoiceAssetId(parsedVoiceId);
        session.setDefaults(buildDefaultsJson(parsedVoiceId, true, true, "update_voice_id"));
        auditDefaultsDrift(session, oldDefaults, session.getDefaults(), oldVoiceAssetId, parsedVoiceId, "update_voice_id");
        session.setUpdateTime(java.time.LocalDateTime.now());
        conversationSessionRepository.save(session);
        return Result.success(true);
    }

    /**
     * 根据 conversationId 删除会话索引
     *
     * @param conversationId 会话 UUID 字符串
     * @return 是否成功删除
     */
    @DeleteMapping("/{conversationId}")
    public Result<Boolean> deleteById(
            @Parameter(name = "conversationId", description = "会话 ID", required = true)
            @PathVariable("conversationId") String conversationId
    ) {
        java.util.UUID cid = UuidUtils.parseLenient(conversationId);
        ConversationSession session = conversationSessionRepository.findById(cid).orElse(null);
        if (session == null) {
            return Result.success(false);
        }
        if (session.getIsDeleted() != null && session.getIsDeleted() == AIChatConstants.DELETED_TRUE) {
            return Result.success(true);
        }
        session.setIsDeleted(AIChatConstants.DELETED_TRUE);
        session.setDeletedAt(java.time.LocalDateTime.now());
        session.setUpdateTime(java.time.LocalDateTime.now());
        conversationSessionRepository.save(session);
        return Result.success(true);
    }

    /**
     * 批量删除会话
     *
     * @param ids 会话 ID 列表（UUID 字符串）
     * @return 成功删除的数量
     */
    @DeleteMapping("/batch")
    public Result<Integer> deleteByIds(
            @Parameter(name = "ids", description = "会话 ID 列表（UUID 字符串）", required = true)
            @RequestBody List<String> ids
    ) {
        if (ids == null || ids.isEmpty()) {
            return Result.success(0);
        }
        int deletedCount = 0;
        for (String idStr : ids) {
            try {
                java.util.UUID id = UuidUtils.parseLenient(idStr);
                if (id != null) {
                    ConversationSession session = conversationSessionRepository.findById(id).orElse(null);
                    if (session != null && (session.getIsDeleted() == null || session.getIsDeleted() == AIChatConstants.DELETED_FALSE)) {
                        session.setIsDeleted(AIChatConstants.DELETED_TRUE);
                        session.setDeletedAt(java.time.LocalDateTime.now());
                        session.setUpdateTime(java.time.LocalDateTime.now());
                        conversationSessionRepository.save(session);
                        deletedCount++;
                    }
                }
            } catch (Exception e) {
                log.debug("Invalid conversationId in deleteByIds: {}", idStr, e);
            }
        }
        return Result.success(deletedCount);
    }

    private ConversationSessionVO toVO(ConversationSession session) {
        ConversationSessionVO vo = new ConversationSessionVO();
        // id 字段由 conversation_id，方便前端直接使用 item.id
        vo.setId(session.getConversationId() != null ? session.getConversationId().toString() : null);
        // Ensure UUID fields are converted to dashed string for VO
        vo.setUserId(session.getUserId() != null ? com.echoes.utils.UuidUtils.toString(session.getUserId()) : null);
        vo.setVoiceAssetId(session.getDefaultVoiceAssetId() != null
                ? com.echoes.utils.UuidUtils.toString(session.getDefaultVoiceAssetId())
                : null);
        BeanUtils.copyProperties(session, vo, "conversationId", "status");
        if (session.getStatus() != null) {
            vo.setStatus(session.getStatus().name());
        }
        return vo;
    }

    private String buildDefaultsJson(java.util.UUID voiceAssetId, boolean strictVoice, boolean streamMode, String source) {
        Map<String, Object> defaults = new LinkedHashMap<>();
        defaults.put("selectedVoiceAssetId", voiceAssetId != null ? voiceAssetId.toString() : null);
        defaults.put("strictVoice", strictVoice);
        defaults.put("streamMode", streamMode);
        defaults.put("source", source);
        defaults.put("updatedAt", LocalDateTime.now().toString());
        try {
            return objectMapper.writeValueAsString(defaults);
        } catch (JsonProcessingException e) {
            log.warn("Failed to serialize conversation defaults, voiceAssetId={}, source={}", voiceAssetId, source, e);
            return "{\"strictVoice\":false,\"streamMode\":true}";
        }
    }

    private void auditDefaultsInitialized(ConversationSession session, String source) {
        if (session == null) {
            return;
        }
        log.info(
                "event=conversation_defaults_initialized conversationId={} userId={} source={} defaults={}",
                session.getConversationId(),
                session.getUserId(),
                source,
                session.getDefaults()
        );
    }

    @SuppressWarnings("unchecked")
    private void auditDefaultsDrift(
            ConversationSession session,
            String oldDefaults,
            String newDefaults,
            java.util.UUID oldVoiceAssetId,
            java.util.UUID newVoiceAssetId,
            String source
    ) {
        if (session == null) {
            return;
        }
        if (Objects.equals(oldDefaults, newDefaults) && Objects.equals(oldVoiceAssetId, newVoiceAssetId)) {
            return;
        }

        Map<String, Object> oldMap = parseDefaultsMap(oldDefaults);
        Map<String, Object> newMap = parseDefaultsMap(newDefaults);
        Map<String, Object> changed = new LinkedHashMap<>();
        for (String k : newMap.keySet()) {
            Object oldVal = oldMap.get(k);
            Object newVal = newMap.get(k);
            if (!Objects.equals(oldVal, newVal)) {
                changed.put(k, Map.of("old", oldVal, "new", newVal));
            }
        }
        if (!Objects.equals(oldVoiceAssetId, newVoiceAssetId)) {
            changed.put("defaultVoiceAssetId", Map.of(
                    "old", oldVoiceAssetId == null ? null : oldVoiceAssetId.toString(),
                    "new", newVoiceAssetId == null ? null : newVoiceAssetId.toString()));
        }

        log.info(
                "event=conversation_defaults_drift conversationId={} userId={} source={} changed={} oldDefaults={} newDefaults={}",
                session.getConversationId(),
                session.getUserId(),
                source,
                changed,
                oldDefaults,
                newDefaults
        );
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseDefaultsMap(String defaultsJson) {
        if (defaultsJson == null || defaultsJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(defaultsJson, Map.class);
        } catch (Exception e) {
            return Map.of("_raw", defaultsJson);
        }
    }
}
