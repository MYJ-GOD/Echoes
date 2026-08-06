package com.echoes.gateway.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

/**
 * 认证白名单配置属性
 * 支持从 Nacos 配置中心动态读取鉴权白名单
 *
 * @author echoes
 */
@Data
@Component
@ConfigurationProperties(prefix = "echoes.gateway.auth.whitelist")
public class AuthWhitelistProperties {

    /**
     * 白名单路径列表
     * 支持 Ant 风格通配符匹配
     */
    private List<String> paths = new ArrayList<>();

    /**
     * 是否启用白名单
     */
    private boolean enabled = true;

    /**
     * 默认白名单路径（当配置为空时使用默认值）
     */
    public List<String> getDefaultPaths() {
        List<String> defaultPaths = new ArrayList<>();
        defaultPaths.add("/api/user/auth/login");
        defaultPaths.add("/api/user/auth/register");
        // 注意：/api/user/auth/validate 已从默认白名单中移除
        // 因为此接口用于验证 Token，本身需要鉴权保护
        defaultPaths.add("/api-docs");
        defaultPaths.add("/api-docs/**");
        defaultPaths.add("/api/*/v3/api-docs/**");
        defaultPaths.add("/v3/api-docs/**");
        defaultPaths.add("/swagger-ui/**");
        defaultPaths.add("/swagger-ui.html");
        defaultPaths.add("/webjars/**");
        defaultPaths.add("/doc.html");
        defaultPaths.add("/favicon.ico");
        defaultPaths.add("/actuator/**");
        return defaultPaths;
    }

    /**
     * 获取有效的白名单路径列表
     * 如果配置为空，返回默认值
     */
    public List<String> getEffectivePaths() {
        if (paths == null || paths.isEmpty()) {
            return getDefaultPaths();
        }
        return paths;
    }
}
