package com.echoes.util;

import com.auth0.jwt.exceptions.JWTVerificationException;
import com.auth0.jwt.interfaces.DecodedJWT;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * JwtUtil 单元测试。
 * 覆盖签发/验证的正反路径，保护网关鉴权链路的核心逻辑。
 */
class JwtUtilTest {

    private static final String SECRET = "echoes-test-secret-key-0123456789";

    @Test
    @DisplayName("签发的 token 能被同一密钥验证通过，且 claims 可读回")
    void generateAndVerify_roundTrip() {
        UUID userId = UUID.randomUUID();
        String token = JwtUtil.generateToken(SECRET, 60_000L, Map.of(
                "userId", userId,
                "username", "alice"
        ));

        DecodedJWT decoded = JwtUtil.verifyToken(SECRET, token);
        assertEquals(userId.toString(), decoded.getClaim("userId").asString());
        assertEquals("alice", decoded.getClaim("username").asString());
    }

    @Test
    @DisplayName("isValidToken 对合法 token 返回 true")
    void isValidToken_validReturnsTrue() {
        String token = JwtUtil.generateToken(SECRET, 60_000L, Map.of("username", "bob"));
        assertTrue(JwtUtil.isValidToken(SECRET, token));
    }

    @Test
    @DisplayName("用错误密钥签发的 token 验证失败")
    void verify_wrongSecretRejected() {
        String token = JwtUtil.generateToken("another-secret-key-value", 60_000L, Map.of("username", "eve"));
        assertFalse(JwtUtil.isValidToken(SECRET, token));
        assertThrows(JWTVerificationException.class, () -> JwtUtil.verifyToken(SECRET, token));
    }

    @Test
    @DisplayName("过期 token 验证失败")
    void verify_expiredRejected() throws InterruptedException {
        // ttl 极短，签发后等待其过期
        String token = JwtUtil.generateToken(SECRET, 1L, Map.of("username", "carol"));
        Thread.sleep(50L);
        assertFalse(JwtUtil.isValidToken(SECRET, token));
    }

    @Test
    @DisplayName("被篡改的 token 验证失败")
    void verify_tamperedRejected() {
        String token = JwtUtil.generateToken(SECRET, 60_000L, Map.of("username", "dave"));
        String tampered = token.substring(0, token.length() - 2) + "xy";
        assertFalse(JwtUtil.isValidToken(SECRET, tampered));
    }

    @Test
    @DisplayName("空密钥或空 token 抛出对应异常")
    void blankInputs_throw() {
        assertThrows(IllegalArgumentException.class,
                () -> JwtUtil.generateToken("", 60_000L, Map.of()));
        assertThrows(IllegalArgumentException.class,
                () -> JwtUtil.generateToken(SECRET, 0L, Map.of()));
        assertThrows(IllegalArgumentException.class,
                () -> JwtUtil.verifyToken("", "some-token"));
        assertThrows(JWTVerificationException.class,
                () -> JwtUtil.verifyToken(SECRET, ""));
        // 空 token 走 isValidToken 应返回 false 而非抛出
        assertFalse(JwtUtil.isValidToken(SECRET, null));
    }
}
