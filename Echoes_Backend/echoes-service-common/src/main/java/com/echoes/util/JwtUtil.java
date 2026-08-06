package com.echoes.util;

import com.auth0.jwt.JWT;
import com.auth0.jwt.JWTVerifier;
import com.auth0.jwt.algorithms.Algorithm;
import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import lombok.extern.slf4j.Slf4j;
import org.springframework.util.StringUtils;

import java.util.Date;
import java.util.Map;
import java.util.UUID;

/**
 * JWT 工具类
 * 提供 Token 生成、验证等功能
 *
 * @author echoes
 */
@Slf4j
public class JwtUtil {

    /**
     * 生成 JWT Token
     *
     * @param secretKey 密钥
     * @param ttlMillis 过期时间（毫秒）
     * @param claims    自定义声明
     * @return JWT Token
     */
    public static String generateToken(String secretKey, long ttlMillis, Map<String, Object> claims) {
        if (!StringUtils.hasText(secretKey)) {
            throw new IllegalArgumentException("JWT secret key is blank");
        }
        if (ttlMillis <= 0) {
            throw new IllegalArgumentException("JWT ttl must be > 0");
        }

        Date now = new Date();
        Date exp = new Date(System.currentTimeMillis() + ttlMillis);

        var builder = JWT.create()
                .withJWTId(UUID.randomUUID().toString())
                .withIssuedAt(now)
                .withExpiresAt(exp);

        if (claims != null) {
            for (Map.Entry<String, Object> entry : claims.entrySet()) {
                Object value = entry.getValue();
                if (value instanceof String) {
                    builder.withClaim(entry.getKey(), (String) value);
                } else if (value instanceof Integer) {
                    builder.withClaim(entry.getKey(), (Integer) value);
                } else if (value instanceof Long) {
                    builder.withClaim(entry.getKey(), (Long) value);
                } else if (value instanceof Boolean) {
                    builder.withClaim(entry.getKey(), (Boolean) value);
                } else if (value instanceof UUID) {
                    builder.withClaim(entry.getKey(), value.toString());
                } else if (value != null) {
                    builder.withClaim(entry.getKey(), value.toString());
                }
            }
        }

        return builder.sign(Algorithm.HMAC256(secretKey));
    }

    /**
     * 验证 JWT Token
     *
     * @param secretKey 密钥
     * @param token     Token
     * @return DecodedJWT
     */
    public static DecodedJWT verifyToken(String secretKey, String token) {
        if (!StringUtils.hasText(secretKey)) {
            throw new IllegalArgumentException("JWT secret key is blank");
        }
        if (!StringUtils.hasText(token)) {
            throw new JWTVerificationException("JWT token is blank");
        }

        JWTVerifier verifier = JWT.require(Algorithm.HMAC256(secretKey)).build();
        return verifier.verify(token);
    }

    /**
     * 判断 JWT Token 是否有效
     *
     * @param secretKey 密钥
     * @param token     Token
     * @return true 表示有效，false 表示无效
     */
    public static boolean isValidToken(String secretKey, String token) {
        try {
            verifyToken(secretKey, token);
            return true;
        } catch (Exception ex) {
            log.debug("JWT validation failed: {}", ex.getMessage());
            return false;
        }
    }
}
