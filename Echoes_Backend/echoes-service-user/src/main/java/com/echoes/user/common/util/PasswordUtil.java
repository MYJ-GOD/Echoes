package com.echoes.user.common.util;

import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * 密码工具类
 * 使用 BCrypt 算法进行密码加密和验证
 * 
 * @author echoes
 */
@Slf4j
public class PasswordUtil {
    
    private static final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder(10);
    
    /**
     * 加密密码
     * 
     * @param rawPassword 原始密码
     * @return 加密后的密码
     */
    public static String encode(String rawPassword) {
        if (rawPassword == null || rawPassword.isEmpty()) {
            throw new IllegalArgumentException("密码不能为空");
        }
        return passwordEncoder.encode(rawPassword);
    }
    
    /**
     * 验证密码
     * 
     * @param rawPassword 原始密码
     * @param encodedPassword 加密后的密码
     * @return true 表示密码匹配，false 表示密码不匹配
     */
    public static boolean matches(String rawPassword, String encodedPassword) {
        if (rawPassword == null || encodedPassword == null) {
            return false;
        }
        try {
            return passwordEncoder.matches(rawPassword, encodedPassword);
        } catch (Exception e) {
            log.error("密码验证失败", e);
            return false;
        }
    }
    
    /**
     * 检查密码是否需要重新加密（用于密码升级）
     * 
     * @param encodedPassword 加密后的密码
     * @return true 表示需要重新加密
     */
    public static boolean needsUpgrade(String encodedPassword) {
        if (encodedPassword == null || encodedPassword.isEmpty()) {
            return true;
        }
        // BCrypt 密码格式：$2a$10$... 或 $2b$10$...
        return !encodedPassword.startsWith("$2a$") && !encodedPassword.startsWith("$2b$");
    }
}
