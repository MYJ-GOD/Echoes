package com.echoes.voice.domain.cache.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.ReactiveRedisTemplate;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

import java.time.Duration;

/**
 * 响应式语音缓存工具类
 * 使用 Redis 实现分布式缓存，与 Mono 完全兼容
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ReactiveVoiceCache {
    
    private final ReactiveRedisTemplate<String, String> redisTemplate;
    private final ObjectMapper objectMapper;
    
    /**
     * 缓存过期时间：24 小时
     */
    private static final Duration CACHE_TTL = Duration.ofHours(24);
    
    /**
     * 缓存键前缀
     */
    private static final String CACHE_PREFIX = "voice:";
    
    /**
     * 获取缓存，如果不存在则执行 supplier 并缓存结果
     * 
     * @param key 缓存键
     * @param supplier 数据提供者（当缓存未命中时调用）
     * @return Mono<JsonNode>
     */
    public Mono<JsonNode> getOrCache(String key, Mono<JsonNode> supplier) {
        String fullKey = CACHE_PREFIX + key;
        
        return redisTemplate.opsForValue()
                .get(fullKey)
                .flatMap(cached -> {
                    // 缓存命中
                    try {
                        JsonNode node = objectMapper.readTree(cached);
                        log.debug("✅ 缓存命中: {}", key);
                        return Mono.just(node);
                    } catch (Exception e) {
                        log.warn("缓存数据解析失败，将重新获取: {}", key, e);
                        return Mono.empty();
                    }
                })
                .switchIfEmpty(
                    // 缓存未命中，执行 supplier 并缓存结果
                    supplier.flatMap(result -> {
                        try {
                            String json = objectMapper.writeValueAsString(result);
                            return redisTemplate.opsForValue()
                                    .set(fullKey, json, CACHE_TTL)
                                    .then(Mono.just(result))
                                    .doOnSuccess(r -> log.debug("💾 已缓存: {}", key));
                        } catch (Exception e) {
                            log.error("缓存数据序列化失败: {}", key, e);
                            // 序列化失败时直接返回结果，不缓存
                            return Mono.just(result);
                        }
                    })
                );
    }
    
    /**
     * 清除指定缓存
     */
    public Mono<Boolean> evict(String key) {
        String fullKey = CACHE_PREFIX + key;
        return redisTemplate.delete(fullKey)
                .map(count -> count > 0)
                .doOnSuccess(deleted -> {
                    if (deleted) {
                        log.debug("🗑️ 已清除缓存: {}", key);
                    }
                });
    }
    
    /**
     * 清除所有语音缓存
     */
    public Mono<Long> evictAll() {
        // Use scan pattern to avoid KEYS blocking in production. Collect keys in pages.
        // ReactiveRedisTemplate.scan requires ScanOptions; build with pattern.
        org.springframework.data.redis.core.ScanOptions options = org.springframework.data.redis.core.ScanOptions.scanOptions()
                .match(CACHE_PREFIX + "*")
                .count(100L)
                .build();
        return redisTemplate.scan(options)
                .buffer(100) // process in batches
                .flatMap((java.util.List<String> batch) -> {
                    if (batch == null || batch.isEmpty()) return Mono.just(0L);
                    String[] keys = batch.toArray(new String[0]);
                    return redisTemplate.delete(keys).map(deletedCount -> deletedCount != null ? deletedCount : 0L);
                })
                .reduce(0L, Long::sum)
                .doOnSuccess(count -> log.info("🗑️ 已清除 {} 个语音缓存", count));
    }
}