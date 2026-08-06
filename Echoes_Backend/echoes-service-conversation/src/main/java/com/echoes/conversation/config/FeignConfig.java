package com.echoes.conversation.config;

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

@Slf4j
@Configuration
@ConditionalOnClass(name = "feign.RequestInterceptor")
public class FeignConfig {

    @Bean
    public Logger.Level feignLoggerLevel() {
        return Logger.Level.BASIC;
    }

    @Bean
    public RequestInterceptor requestInterceptor() {
        return new RequestInterceptor() {
            @Override
            public void apply(RequestTemplate template) {
                ServletRequestAttributes attributes = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
                if (attributes != null) {
                    HttpServletRequest request = attributes.getRequest();

                    String authorization = request.getHeader("Authorization");
                    if (authorization != null) {
                        template.header("Authorization", authorization);
                    }

                    String contentType = request.getHeader("Content-Type");
                    if (contentType != null) {
                        template.header("Content-Type", contentType);
                    }

                    // 统一使用 X-USER-ID Header（与 voice 服务保持一致）
                    String userId = request.getHeader("X-USER-ID");
                    if (userId != null) {
                        template.header("X-USER-ID", userId);
                    }
                }
            }
        };
    }
}
