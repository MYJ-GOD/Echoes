package com.echoes.voice.config;

import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * WebClient配置
 * 配置负载均衡的WebClient.Builder
 */
@Configuration
@ConditionalOnClass(WebClient.class)
public class WebClientConfig {

    /**
     * 创建负载均衡的WebClient.Builder
     *
     * @return WebClient.Builder实例
     */
    @Bean
    @LoadBalanced
    public WebClient.Builder webClientBuilder() {
        return WebClient.builder();
    }
}
