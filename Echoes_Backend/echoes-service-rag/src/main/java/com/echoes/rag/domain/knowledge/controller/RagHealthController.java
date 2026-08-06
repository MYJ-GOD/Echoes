package com.echoes.rag.domain.knowledge.controller;

import org.springframework.boot.SpringBootVersion;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/rag")
public class RagHealthController {

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> result = new HashMap<>();
        result.put("status", "UP");
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", "Echoes-RAG service is running");
        result.put("jdk", System.getProperty("java.version"));
        result.put("springBoot", SpringBootVersion.getVersion());
        return result;
    }

    @GetMapping("/ready")
    public Map<String, Object> ready() {
        Map<String, Object> result = new HashMap<>();
        result.put("ready", true);
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", "Echoes-RAG service is ready");
        return result;
    }
}