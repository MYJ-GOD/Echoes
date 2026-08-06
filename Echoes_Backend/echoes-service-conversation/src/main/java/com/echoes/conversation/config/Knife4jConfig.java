package com.echoes.conversation.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import io.swagger.v3.oas.models.servers.Server;
import org.springdoc.core.customizers.GlobalOperationCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * Knife4j/OpenAPI 配置类
 * 用于配置 API 文档的基本信息和安全认证
 */
@Configuration
public class Knife4jConfig {

    /**
     * OpenAPI 配置
     * 配置 API 文档的基本信息、服务器地址和安全认证方案
     */
    @Bean
    public OpenAPI springOpenApi() {
        // JWT 安全配置方案
        SecurityScheme securityScheme = new SecurityScheme()
                .type(SecurityScheme.Type.APIKEY)
                .in(SecurityScheme.In.HEADER)
                .name("token")
                .description("JWT Token，从登录接口获取");

        return new OpenAPI()
                .info(new Info()
                        .title("Echoes 对话服务 API")
                        .description("Echoes 微服务系统 - 对话服务 API 文档\n\n" +
                                "## 功能说明\n" +
                                "- AI 对话（基于阿里云百炼大模型）\n" +
                                "- 流式对话响应\n" +
                                "- 会话管理（创建、查询、删除）\n" +
                                "- 消息管理（查询历史消息）\n" +
                                "- JWT Token 认证\n\n" +
                                "## 认证说明\n" +
                                "1. 调用登录接口获取 Token\n" +
                                "2. 在请求头中添加 `token: {your-token}`\n" +
                                "3. 或者点击右上角的「Authorize」按钮输入 Token")
                        .version("1.0.0")
                        .contact(new Contact()
                                .name("Echoes Team")
                                .email("support@echoes.com"))
                        .license(new License()
                                .name("Apache 2.0")
                                .url("https://www.apache.org/licenses/LICENSE-2.0.html")))
                .servers(List.of(
                        new Server().url("http://localhost:18082").description("本地开发环境"),
                        new Server().url("http://localhost:18080/api/chat").description("通过 Gateway 访问")
                ))
                .components(new Components()
                        .addSecuritySchemes("token", securityScheme));
    }

    /**
     * 全局操作自定义器
     * 为所有接口自动添加安全要求（JWT Token）
     */
    @Bean
    public GlobalOperationCustomizer operationCustomizer() {
        return (operation, method) -> {
            // 为所有接口添加 JWT Token 安全要求
            operation.addSecurityItem(new SecurityRequirement().addList("token"));
            return operation;
        };
    }
}

