package com.echoes.conversation.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * DashScope 配置属性
 * 
 * 参考 DashScope Python SDK 配置方式：
 * - base_http_api_url: API 基础 URL（默认：https://dashscope.aliyuncs.com/api/v1）
 * - model: 使用的模型名称（如 qwen-turbo, qwen2.5-vl-32b-instruct 等）
 * - api_key: API Key（必填）
 */
@Data
@ConfigurationProperties(prefix = "spring.ai.dashscope")
public class DashScopeProperties {

    private String apiKey;

    private String baseUrl;

    /**
     *
     * 常用模型：
     * - qwen-turbo: 通义千问 Turbo 版本（快速响应）
     * - qwen-plus: 通义千问 Plus 版本（更强能力）
     * - qwen-max: 通义千问 Max 版本（最强能力）
     * - qwen2.5-vl-32b-instruct: 多模态视觉语言模型（支持图像识别）
     */
    private String model;
    
    /**
     * Agent 配置（可选）
     */
    private Agent agent = new Agent();
    
    /**
     * 业务空间ID（可选）
     * 注意：Spring Boot 配置中使用 workspace-id，会自动绑定到 workspaceId
     */
    private String workspaceId;
    
    @Data
    public static class Agent {
        /**
         * 大模型应用ID（如果使用 Agent 模式）
         */
        private String appId;
    }
}

