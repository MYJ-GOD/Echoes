package com.echoes.voice.domain.cache.controller;

import com.echoes.voice.domain.cache.service.ReactiveVoiceCache;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

/**
 * 语音缓存管理接口
 * 用于查看和管理 Redis 缓存
 */
@RestController
@RequestMapping("/internal/voice/cache")
@RequiredArgsConstructor
public class VoiceCacheController {
    
    private final ReactiveVoiceCache voiceCache;
    
    /**
     * 清除指定缓存
     * POST /cache/evict?key=voice1:你好
     */
    @PostMapping("/evict")
    public Mono<Map<String, Object>> evictCache(@RequestParam String key) {
        return voiceCache.evict(key)
                .map(deleted -> {
                    Map<String, Object> result = new HashMap<>();
                    result.put("success", deleted);
                    result.put("message", deleted ? "缓存已清除" : "缓存不存在");
                    result.put("key", key);
                    return result;
                });
    }
    
    /**
     * 清除所有语音缓存
     * POST /cache/evict-all
     */
    @PostMapping("/evict-all")
    public Mono<Map<String, Object>> evictAllCache() {
        return voiceCache.evictAll()
                .map(count -> {
                    Map<String, Object> result = new HashMap<>();
                    result.put("success", true);
                    result.put("message", "已清除 " + count + " 个缓存");
                    result.put("count", count);
                    return result;
                });
    }
}