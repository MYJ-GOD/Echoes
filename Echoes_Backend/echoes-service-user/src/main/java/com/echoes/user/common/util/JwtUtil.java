package com.echoes.user.common.util;

import com.auth0.jwt.interfaces.DecodedJWT;
import com.echoes.user.config.JwtProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
@RequiredArgsConstructor
public class JwtUtil {

    private final JwtProperties jwtProperties;

    public String generateUserToken(Map<String, Object> claims) {
        return com.echoes.util.JwtUtil.generateToken(jwtProperties.getUserSecretKey(), jwtProperties.getUserTtl(), claims);
    }

    public String generateAdminToken(Map<String, Object> claims) {
        return com.echoes.util.JwtUtil.generateToken(jwtProperties.getAdminSecretKey(), jwtProperties.getAdminTtl(), claims);
    }

    public DecodedJWT validateUserToken(String token) {
        return com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
    }

    public boolean isValidUserToken(String token) {
        return com.echoes.util.JwtUtil.isValidToken(jwtProperties.getUserSecretKey(), token);
    }
}
