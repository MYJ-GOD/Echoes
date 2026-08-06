package com.echoes.user.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * JWT 配置属性类
 * 从配置文件中读取 JWT 相关配置
 */
@Data
@Component
@ConfigurationProperties(prefix = "sky.jwt")
public class JwtProperties {

    /**
     * 用户 JWT 密钥
     * 从 Nacos 配置 sky.jwt.user-secret-key 读取
     */
    private String userSecretKey;

    /**
     * 用户 Token 过期时间（毫秒）
     */
    private long userTtl = 7200000L;

    /**
     * 用户 Token 名称
     */
    private String userTokenName = "token";

    /**
     * 管理员 JWT 密钥
     * 从 Nacos 配置 sky.jwt.admin-secret-key 读取
     */
    private String adminSecretKey;

    /**
     * 管理员 Token 过期时间（毫秒）
     */
    private long adminTtl = 7200000L;
}
