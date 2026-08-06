package com.echoes.user.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Spring Security 配置类
 * 配置密码编码器
 */
@Configuration
public class SecurityConfig {

    /**
     * 配置密码编码器
     * 使用 BCrypt 算法进行密码加密
     * 
     * @return PasswordEncoder Bean
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
