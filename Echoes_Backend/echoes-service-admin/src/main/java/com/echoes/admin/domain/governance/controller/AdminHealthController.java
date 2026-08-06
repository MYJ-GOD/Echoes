package com.echoes.admin.domain.governance.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/admin")
public class AdminHealthController {

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> result = new HashMap<>();
        result.put("status", "UP");
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", "Echoes-Admin 服务运行正常");
        result.put("jdk", System.getProperty("java.version"));
        result.put("springBoot", org.springframework.boot.SpringBootVersion.getVersion());
        return result;
    }

    @GetMapping("/ready")
    public Map<String, Object> ready() {
        Map<String, Object> result = new HashMap<>();
        result.put("ready", true);
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", "Echoes-Admin 服务已就绪");
        return result;
    }
}
