package com.echoes.gateway.domain.gateway.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 健康检查控制器
 * 用于测试服务是否正常运行
 */
@RestController
@RequestMapping("/health")
public class HealthController {

    @GetMapping
    public Map<String, Object> health() {
        Map<String, Object> result = new HashMap<>();
        result.put("status", "UP");
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", "Echoes 服务运行正常");
        result.put("jdk", System.getProperty("java.version"));
        result.put("springBoot", org.springframework.boot.SpringBootVersion.getVersion());
        return result;
    }

}


