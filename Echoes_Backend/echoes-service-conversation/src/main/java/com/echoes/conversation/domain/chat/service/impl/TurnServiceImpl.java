package com.echoes.conversation.domain.chat.service.impl;

import com.echoes.conversation.common.constants.AIChatConstants;
import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;
import com.echoes.conversation.domain.chat.enums.AIChatEnum;
import com.echoes.conversation.domain.chat.repository.ConversationTurnRepository;
import com.echoes.conversation.domain.chat.service.ITurnService;
import com.echoes.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.TimeUnit;

/**
 * 瀵硅瘽杞鏈嶅姟瀹炵幇
 * 绠＄悊瀵硅瘽涓瘡涓疆娆＄殑鐢熷懡鍛ㄦ湡锛堝紑濮嬨€佸畬鎴愩€佸け璐ワ級
 * 鏀寔骞傜瓑鎬ф帶鍒跺拰Redis鐑姸鎬佺紦瀛?
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TurnServiceImpl implements ITurnService {

    private final ConversationTurnRepository turnRepository;
    private final RedisTemplate<String, Object> redisTemplate;

    private static final String REDIS_KEY_PREFIX = "turn:";
    private static final long REDIS_KEY_TTL_DAYS = 1;
    private static final long EVENTS_KEY_TTL_DAYS = 7;
    private static final String IDEMPOTENCY_CONFLICT_METRIC_KEY_PREFIX = "metrics:conversation:idempotency_conflict:";

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ConversationTurn startTurn(java.util.UUID conversationId, String turnId, java.util.UUID userId, String idempotencyKey, byte[] payloadHash) {
        if (userId == null) {
            throw new BusinessException(AIChatEnum.SESSION_USER_ID_REQUIRED.getCode(), AIChatEnum.SESSION_USER_ID_REQUIRED.getMessage());
        }
        // 1. Check MySQL for existing turn (Authoritative)
        ConversationTurn existing = turnRepository.findByConversationIdAndTurnId(conversationId, turnId);

        if (existing != null) {
            // 骞傜瓑鏍￠獙閫昏緫 (Rule A/B/C from Architecture Doc 5.x.3)

            // Rule C: Payload Mismatch
            if (payloadHash != null && existing.getPayloadHash() != null && !java.util.Arrays.equals(payloadHash, existing.getPayloadHash())) {
                recordIdempotencyConflict(conversationId, turnId, idempotencyKey, "payload_mismatch_with_existing_turn");
                throw new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), "CONFLICT: Turn ID exists but payload mismatch");
            }

            // Rule A: Same Turn ID -> Return existing (Caller should handle REPLAY/ATTACH based on status)
            log.info("Turn existing: {}, status: {}", turnId, existing.getStatus());
            return existing;
        }

        // Rule B: Same idempotency_key but different turn_id -> 409 conflict
        if (idempotencyKey != null) {
            ConversationTurn byIdempo = turnRepository.findByConversationIdAndIdempotencyKey(conversationId, idempotencyKey);
            if (byIdempo != null) {
                recordIdempotencyConflict(conversationId, turnId, idempotencyKey, "idempotency_key_reused_with_different_turn");
                throw new BusinessException(AIChatEnum.SESSION_NOT_EXISTS.getCode(), "CONFLICT: idempotency_key already used with different turn_id");
            }
        }

        // 2. Create new Turn in MySQL (RUNNING)
        ConversationTurn newTurn = ConversationTurn.builder()
                .id(java.util.UUID.randomUUID())
                .turnId(turnId)
                .conversationId(conversationId)
                .userId(userId)
                .idempotencyKey(idempotencyKey)
                .payloadHash(payloadHash)
                .status(AIChatConstants.TURN_STATUS_RUNNING)
                .retryable(0)
                .startTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();

        ConversationTurn saved = turnRepository.save(newTurn);

        // 3. Initialize Redis Hot State
        String redisKey = getRedisKey(conversationId, turnId);
        redisTemplate.opsForHash().put(redisKey, "status", AIChatConstants.TURN_STATUS_RUNNING);
        redisTemplate.opsForHash().put(redisKey, "start_time", System.currentTimeMillis());
        redisTemplate.expire(redisKey, REDIS_KEY_TTL_DAYS, TimeUnit.DAYS);

        log.info("Turn started: {}", turnId);
        return saved;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void completeTurn(String turnId, String finalMessageId) {
        ConversationTurn turn = turnRepository.findByTurnId(turnId);
        if (turn == null) {
            log.error("Attempt to complete non-existent turn: {}", turnId);
            return;
        }

        // Update MySQL
        turn.setStatus(AIChatConstants.TURN_STATUS_SUCCESS);
        turn.setFinalMessageId(finalMessageId);
        turn.setEndTime(LocalDateTime.now());
        turn.setUpdateTime(LocalDateTime.now());
        turnRepository.save(turn);

        // Update Redis (Clear hot state or mark success)
        // We keep it for a while for potential query/replay
        String redisKey = getRedisKey(turn.getConversationId(), turnId);
        redisTemplate.opsForHash().put(redisKey, "status", AIChatConstants.TURN_STATUS_SUCCESS);
        if (finalMessageId != null) {
            redisTemplate.opsForHash().put(redisKey, "final_message_id", finalMessageId);
        }

        log.info("Turn completed: {}", turnId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void failTurn(String turnId, String errorMessage, String errorStage, boolean retryable) {
        String code = "INTERNAL_ERROR";
        if (errorMessage != null && errorMessage.startsWith("CONFLICT")) {
            code = "CONFLICT";
        } else if (errorMessage != null && errorMessage.contains("USER_ID_REQUIRED")) {
            code = "USER_ID_REQUIRED";
        }
        failTurn(turnId, code, errorMessage, errorStage, retryable);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void failTurn(String turnId, String errorCode, String errorMessage, String errorStage, boolean retryable) {
        ConversationTurn turn = turnRepository.findByTurnId(turnId);
        if (turn == null) {
            log.error("Attempt to fail non-existent turn: {}", turnId);
            return;
        }

        // Update MySQL
        turn.setStatus(AIChatConstants.TURN_STATUS_FAILED);
        turn.setErrorCode(errorCode == null || errorCode.isBlank() ? "INTERNAL_ERROR" : errorCode);
        turn.setErrorStage(errorStage);
        turn.setRetryable(retryable ? 1 : 0);
        turn.setEndTime(LocalDateTime.now());
        turn.setUpdateTime(LocalDateTime.now());
        turnRepository.save(turn);

        // Update Redis
        String redisKey = getRedisKey(turn.getConversationId(), turnId);
        redisTemplate.opsForHash().put(redisKey, "status", AIChatConstants.TURN_STATUS_FAILED);

        log.warn("Turn failed: {}, reason: {}", turnId, errorMessage);
    }

    @Override
    public boolean exists(String turnId) {
        return turnRepository.existsByTurnId(turnId);
    }

    /**
     * 鐢熸垚Redis閿?
     *
     * @param conversationId 浼氳瘽ID
     * @param turnId         杞ID
     * @return Redis閿悕
     */
    private String getRedisKey(java.util.UUID conversationId, String turnId) {
        return REDIS_KEY_PREFIX + conversationId + ":" + turnId;
    }

    @Override
    public long nextSeq(java.util.UUID conversationId, String turnId) {
        String seqKey = getRedisKey(conversationId, turnId) + ":last_seq";
        Long seq = redisTemplate.opsForValue().increment(seqKey, 1);
        try {
            // Ensure TTL is present for seq key
            redisTemplate.expire(seqKey, EVENTS_KEY_TTL_DAYS, TimeUnit.DAYS);
        } catch (Exception e) {
            log.debug("Failed to set TTL for seqKey {}: {}", seqKey, e.getMessage());
        }
        return seq != null ? seq.longValue() : 0L;
    }

    @Override
    public void appendEvent(java.util.UUID conversationId, String turnId, long seq, String eventJson) {
        try {
            String eventsKey = "turn_event:" + conversationId + ":" + turnId;
            // Store the event JSON as-is (should include seq field)
            redisTemplate.opsForList().rightPush(eventsKey, eventJson);
            // set TTL to 7 days (architecture allows 24h~7d)
            redisTemplate.expire(eventsKey, EVENTS_KEY_TTL_DAYS, TimeUnit.DAYS);
        } catch (Exception e) {
            log.error("Failed to append event to redis for turn {}: {}", turnId, e.getMessage(), e);
        }
    }

    @Override
    public java.util.List<String> fetchEvents(java.util.UUID conversationId, String turnId) {
        try {
            String eventsKey = "turn_event:" + conversationId + ":" + turnId;
            java.util.List<Object> range = redisTemplate.opsForList().range(eventsKey, 0, -1);
            if (range == null || range.isEmpty()) return java.util.Collections.emptyList();
            java.util.List<String> result = new java.util.ArrayList<>(range.size());
            for (Object o : range) {
                result.add(o != null ? o.toString() : null);
            }
            return result;
        } catch (Exception e) {
            log.error("Failed to fetch events for turn {}: {}", turnId, e.getMessage(), e);
            return java.util.Collections.emptyList();
        }
    }

    private void recordIdempotencyConflict(java.util.UUID conversationId, String turnId, String idempotencyKey, String reason) {
        String day = LocalDate.now().format(DateTimeFormatter.BASIC_ISO_DATE);
        String redisMetricKey = IDEMPOTENCY_CONFLICT_METRIC_KEY_PREFIX + day;
        Long count = redisTemplate.opsForValue().increment(redisMetricKey, 1);
        redisTemplate.expire(redisMetricKey, 30, TimeUnit.DAYS);

        log.warn(
                "event=idempotency_conflict conversationId={} turnId={} idempotencyKey={} reason={} day={} conflictCount={}",
                conversationId,
                turnId,
                idempotencyKey,
                reason,
                day,
                count
        );
    }
}
