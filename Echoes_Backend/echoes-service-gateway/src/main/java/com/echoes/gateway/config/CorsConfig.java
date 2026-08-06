package com.echoes.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsWebFilter;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

/**
 * 跨域配置
 * 配置Gateway的CORS策略，允许前端应用跨域访问
 */
@Configuration
public class CorsConfig {

    /**
     * 允许的来源地址模式
     */
    private static final List<String> ALLOWED_ORIGIN_PATTERNS = Arrays.asList(
        "http://localhost:*",
        "http://127.0.0.1:*"
    );

    /**
     * 允许的HTTP方法
     */
    private static final List<String> ALLOWED_METHODS = Arrays.asList("GET", "POST", "PUT", "DELETE", "OPTIONS");

    /**
     * 允许的HTTP头
     */
    private static final List<String> ALLOWED_HEADERS = Arrays.asList("*");

    /**
     * 是否允许携带凭证（Cookie、Authorization头等）
     */
    private static final boolean ALLOW_CREDENTIALS = true;

    /**
     * 预检请求的缓存时间（秒）
     */
    private static final long MAX_AGE = 3600L;

    /**
     * 创建CORS WebFilter
     *
     * @return CorsWebFilter实例
     */
    @Bean
    public CorsWebFilter corsWebFilter() {
        CorsConfiguration config = new CorsConfiguration();
        config.setAllowedOriginPatterns(ALLOWED_ORIGIN_PATTERNS);
        config.setAllowedMethods(ALLOWED_METHODS);
        config.setAllowedHeaders(ALLOWED_HEADERS);
        config.setAllowCredentials(ALLOW_CREDENTIALS);
        config.setMaxAge(MAX_AGE);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return new CorsWebFilter(source);
    }
}


