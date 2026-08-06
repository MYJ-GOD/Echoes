package com.echoes.conversation.domain.chat.service.impl;

import com.echoes.exception.BusinessException;
import com.echoes.conversation.domain.chat.service.ITurnEventService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Turn事件服务实现
 * 基于Redis的对话轮次事件缓冲服务
 *
 * Key设计：
 *  - 序列键: turn:{sessionId}:{turnId}:seq  (string/incr)
 *  - 事件列表: turn:{sessionId}:{turnId}:events  (JSON列表)
 *
 * TTL默认设置为3天，用于支持事件恢复
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TurnEventServiceImpl implements ITurnEventService {

    private final RedisTemplate<String, Object> redisTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private static final long EVENTS_TTL_DAYS = 3;

    /**
     * 生成序列键
     *
     * @param sessionId 会话ID
     * @param turnId    轮次ID
     * @return Redis键名
     */
    private String seqKey(String sessionId, String turnId) {
        return "turn:" + sessionId + ":" + turnId + ":seq";
    }

    /**
     * 生成事件列表键
     *
     * @param sessionId 会话ID
     * @param turnId    轮次ID
     * @return Redis键名
     */
    private String eventsKey(String sessionId, String turnId) {
        return "turn:" + sessionId + ":" + turnId + ":events";
    }

    /**
     * 追加事件到缓冲区
     *
     * @param sessionId      会话ID
     * @param turnId         轮次ID
     * @param type           事件类型
     * @param data           事件数据
     * @param traceId        追踪ID
     * @param protocolVersion 协议版本
     * @return 事件的JSON字符串
     */
    @Override
    public String appendEvent(String sessionId, String turnId, String type, Object data, String traceId, String protocolVersion) {
        try {
            String seqKey = seqKey(sessionId, turnId);
            String eventsKey = eventsKey(sessionId, turnId);

            // Atomic increment seq
            Long seq = redisTemplate.opsForValue().increment(seqKey, 1);
            if (seq == null) {
                seq = 0L;
            }

            Map<String, Object> event = new HashMap<>();
            event.put("type", type);
            event.put("trace_id", traceId);
            event.put("session_id", sessionId);
            event.put("turn_id", turnId);
            event.put("seq", seq);
            event.put("protocol_version", protocolVersion);
            event.put("ts", Instant.now().toEpochMilli());
            if (data != null) {
                event.put("data", data);
            }

            String json = objectMapper.writeValueAsString(event);

            // Push to events list
            redisTemplate.opsForList().rightPush(eventsKey, json);

            // Set TTLs
            try {
                redisTemplate.expire(seqKey, EVENTS_TTL_DAYS, TimeUnit.DAYS);
                redisTemplate.expire(eventsKey, EVENTS_TTL_DAYS, TimeUnit.DAYS);
            } catch (Exception e) {
                log.debug("Failed to set TTL on redis keys for session {} turn {}: {}", sessionId, turnId, e.getMessage());
            }

            return json;
        } catch (Exception e) {
            log.error("Failed to append turn event for session {} turn {}: {}", sessionId, turnId, e.getMessage(), e);
            throw new BusinessException("Failed to append turn event: " + e.getMessage());
        }
    }
}


