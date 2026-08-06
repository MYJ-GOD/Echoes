package com.echoes.conversation.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * echoes-langgraph（Agent 编排服务）配置
 */
@Data
@Component
@ConfigurationProperties(prefix = "echoes.langgraph")
public class LanggraphProperties {

    /**
     * echoes-langgraph 服务地址（含 /api/v1 前缀）
     */
    private String url = "http://localhost:8088/api/v1";
}
