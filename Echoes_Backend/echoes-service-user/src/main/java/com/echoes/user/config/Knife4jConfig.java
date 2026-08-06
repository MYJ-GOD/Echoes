package com.echoes.user.config;

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
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.HandlerMethod;

import java.util.List;
import java.util.Set;

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
                        .title("Echoes 用户服务 API")
                        .description("Echoes 微服务系统 - 用户服务 API 文档\n\n" +
                                "## 功能说明\n" +
                                "- 用户注册、登录、登出\n" +
                                "- 用户个人信息管理\n" +
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
                        new Server().url("http://localhost:18081").description("本地开发环境"),
                        new Server().url("http://localhost:18080/api/user").description("通过 Gateway 访问")
                ))
                .components(new Components()
                        .addSecuritySchemes("token", securityScheme));
    }

    /**
     * 全局操作自定义器
     * 为需要认证的接口自动添加安全要求（JWT Token）
     * 排除登录、注册等公开接口
     */
    @Bean
    public GlobalOperationCustomizer operationCustomizer() {
        // 不需要 token 的接口路径集合
        Set<String> publicPaths = Set.of(
                "/auth/login",
                "/auth/register",
                "/auth/validate"
        );
        
        return (operation, handlerMethod) -> {
            // 获取接口路径
            String path = getOperationPath(handlerMethod);
            
            // 如果是不需要认证的公开接口，则不添加 token 要求
            if (path != null && publicPaths.contains(path)) {
                return operation;
            }
            
            // 为其他接口添加 JWT Token 安全要求
            operation.addSecurityItem(new SecurityRequirement().addList("token"));
            return operation;
        };
    }
    
    /**
     * 从 HandlerMethod 中提取接口路径
     */
    private String getOperationPath(HandlerMethod handlerMethod) {
        if (handlerMethod == null) {
            return null;
        }
        
        // 获取类级别的 RequestMapping
        RequestMapping classMapping = handlerMethod.getBeanType().getAnnotation(RequestMapping.class);
        String classPath = "";
        if (classMapping != null && classMapping.value().length > 0) {
            classPath = classMapping.value()[0];
            // 确保路径以 / 开头
            if (!classPath.startsWith("/")) {
                classPath = "/" + classPath;
            }
        }
        
        // 获取方法级别的 RequestMapping
        String methodPath = "";
        RequestMapping methodMapping = handlerMethod.getMethodAnnotation(RequestMapping.class);
        if (methodMapping != null && methodMapping.value().length > 0) {
            methodPath = methodMapping.value()[0];
        } else {
            PostMapping postMapping = handlerMethod.getMethodAnnotation(PostMapping.class);
            if (postMapping != null && postMapping.value().length > 0) {
                methodPath = postMapping.value()[0];
            } else {
                GetMapping getMapping = handlerMethod.getMethodAnnotation(GetMapping.class);
                if (getMapping != null && getMapping.value().length > 0) {
                    methodPath = getMapping.value()[0];
                } else {
                    PutMapping putMapping = handlerMethod.getMethodAnnotation(PutMapping.class);
                    if (putMapping != null && putMapping.value().length > 0) {
                        methodPath = putMapping.value()[0];
                    } else {
                        DeleteMapping deleteMapping = handlerMethod.getMethodAnnotation(DeleteMapping.class);
                        if (deleteMapping != null && deleteMapping.value().length > 0) {
                            methodPath = deleteMapping.value()[0];
                        } else {
                            PatchMapping patchMapping = handlerMethod.getMethodAnnotation(PatchMapping.class);
                            if (patchMapping != null && patchMapping.value().length > 0) {
                                methodPath = patchMapping.value()[0];
                            }
                        }
                    }
                }
            }
        }
        
        // 如果方法路径不为空，确保以 / 开头
        if (!methodPath.isEmpty() && !methodPath.startsWith("/")) {
            methodPath = "/" + methodPath;
        }
        
        // 拼接完整路径
        String fullPath = classPath + methodPath;
        // 规范化路径：移除多余的斜杠
        fullPath = fullPath.replaceAll("//+", "/");
        // 确保路径以 / 开头
        if (!fullPath.startsWith("/")) {
            fullPath = "/" + fullPath;
        }
        
        return fullPath;
    }
}

