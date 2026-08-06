package com.echoes.admin.config;

import feign.Logger;
import feign.RequestInterceptor;
import feign.RequestTemplate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpServletRequest;

/**
 * Feign 客户端配置
 * 用于服务间调用时传递请求头（Authorization、X-USER-ID 等）
 */
@Slf4j
@Configuration
@ConditionalOnClass(name = "feign.RequestInterceptor")
public class FeignConfig {

    /**
     * 配置 Feign 日志级别
     *
     * @return 日志级别
     */
    @Bean
    public Logger.Level feignLoggerLevel() {
        return Logger.Level.BASIC;
    }

    /**
     * 配置请求拦截器
     * 用于在 Feign 调用时透传请求头
     *
     * @return 请求拦截器
     */
    @Bean
    public RequestInterceptor requestInterceptor() {
        return new RequestInterceptor() {
            @Override
            public void apply(RequestTemplate template) {
                ServletRequestAttributes attributes = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
                if (attributes != null) {
                    HttpServletRequest request = attributes.getRequest();

                    // 透传 Authorization
                    String authorization = request.getHeader("Authorization");
                    if (authorization != null) {
                        template.header("Authorization", authorization);
                    }

                    // 透传 X-USER-ID（统一使用大写下划线格式）
                    String userId = request.getHeader("X-USER-ID");
                    if (userId != null) {
                        template.header("X-USER-ID", userId);
                    }

                    // 透传 X-INTERNAL（内部服务调用标识）
                    String internal = request.getHeader("X-INTERNAL");
                    if (internal != null) {
                        template.header("X-INTERNAL", internal);
                    }
                }
            }
        };
    }
}
