package com.echoes.conversation.config;

import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.stereotype.Component;

/**
 * DashScope 配置验证器
 * 在应用启动时验证配置是否正确加载
 */
@Slf4j
@Component
@RequiredArgsConstructor
@ConditionalOnBean(DashScopeProperties.class)
public class DashScopeConfigValidator {
    
    private final DashScopeProperties dashScopeProperties;
    
    @PostConstruct
    public void validateConfig() {
        log.info("=== DashScope 配置验证 ===");
        log.info("API Key: {}", maskApiKey(dashScopeProperties.getApiKey()));
        log.info("Base URL: {}", dashScopeProperties.getBaseUrl());
        log.info("Model: {}", dashScopeProperties.getModel());
        
        // 验证必填配置
        if (dashScopeProperties.getApiKey() == null || dashScopeProperties.getApiKey().trim().isEmpty()) {
            log.error("❌ DashScope API Key 未配置！请在 Nacos 中配置 spring.ai.dashscope.api-key");
        } else {
            log.info("✅ DashScope API Key 已配置");
        }
        
        if (dashScopeProperties.getModel() == null || dashScopeProperties.getModel().trim().isEmpty()) {
            log.warn("⚠️  DashScope Model 未配置，将使用默认模型");
        } else {
            log.info("✅ DashScope Model: {}", dashScopeProperties.getModel());
        }
        
        log.info("✅ DashScope 配置验证完成，ChatClient 将在首次使用时初始化");
        log.info("=== DashScope 配置验证完成 ===");
    }
    
    /**
     * 掩码处理 API Key，只显示前4位和后4位
     */
    private String maskApiKey(String apiKey) {
        if (apiKey == null || apiKey.length() <= 8) {
            return "***";
        }
        return apiKey.substring(0, 4) + "..." + apiKey.substring(apiKey.length() - 4);
    }
}

