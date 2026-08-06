package com.echoes.gateway.domain.gateway.filter;

import com.echoes.gateway.common.constants.JwtClaimsConstant;
import com.echoes.gateway.common.result.Result;
import com.echoes.gateway.config.AuthWhitelistProperties;
import com.echoes.gateway.config.JwtProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.auth0.jwt.interfaces.DecodedJWT;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.util.AntPathMatcher;
import org.springframework.util.StringUtils;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * JWT认证过滤器
 * 在网关层统一处理JWT Token验证
 *
 * 注意：直接在网关层验证JWT Token，不需要调用用户服务
 * JWT Token本身是自包含的，可以在网关层直接验证签名和过期时间
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter implements GlobalFilter, Ordered {

    private final JwtProperties jwtProperties;
    private final ObjectMapper objectMapper;
    private final AuthWhitelistProperties whitelistProperties;

    /**
     * 过滤器执行顺序，数字越小越先执行
     */
    private static final int FILTER_ORDER = -100;

    /**
     * AntPathMatcher 实例，用于路径匹配
     */
    private static final AntPathMatcher PATH_MATCHER = new AntPathMatcher();
    
    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();
        
        // 白名单直接放行
        if (isWhitelist(path)) {
            log.debug("白名单路径，直接放行: {}", path);
            return chain.filter(exchange);
        }
        
        // 提取Token
        String token = extractToken(request);
        log.debug("Gateway incoming request path={}, has Authorization header={}", path, request.getHeaders().getFirst("Authorization") != null);
        if (!StringUtils.hasText(token)) {
            log.warn("请求缺少Token: path={}", path);
            return unauthorized(exchange, "未授权，请先登录");
        }
        
        // 直接在网关层验证Token（使用JWT工具类）
        // JWT Token本身是自包含的，可以验证签名和过期时间，不需要调用用户服务
        try {
            // 验证Token是否有效（检查签名和过期时间）
            if (!com.echoes.util.JwtUtil.isValidToken(jwtProperties.getUserSecretKey(), token)) {
                log.warn("Token验证失败: path={}", path);
                return unauthorized(exchange, "Token无效或已过期");
            }
            
            // Token有效，解析用户信息并添加到请求头
            DecodedJWT decodedJWT = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
            String userIdStr = decodedJWT.getClaim(JwtClaimsConstant.USER_ID).asString();
            String username = decodedJWT.getClaim(JwtClaimsConstant.USERNAME).asString();
            String name = decodedJWT.getClaim(JwtClaimsConstant.NAME).asString();
            String userId = userIdStr;
            log.debug("Gateway parsed token -> userId={}, username={}, path={}", userId, username, path);
            
            // 添加自定义请求头，传递给下游服务
            ServerHttpRequest mutatedRequest = request.mutate()
                .header("X-USER-ID", userId != null ? userId : "")
                .header("X-USER-NAME", username != null ? username : "")
                .header("X-USER-NAME-VALUE", name != null ? name : "")
                .header("Authorization", "Bearer " + token)
                .build();
            
            log.debug("Token验证成功，添加用户信息到请求头并转发: userId={}, username={}, forwardedPath={}", userId, username, path);
            return chain.filter(exchange.mutate().request(mutatedRequest).build());
        } catch (Exception e) {
            log.error("Token验证异常: path={}", path, e);
            return unauthorized(exchange, "Token验证失败，请重新登录");
        }
    }
    
    /**
     * 检查路径是否在白名单中
     * 使用 AntPathMatcher 支持通配符匹配
     */
    private boolean isWhitelist(String path) {
        if (!whitelistProperties.isEnabled()) {
            log.debug("白名单已禁用，路径：{}", path);
            return false;
        }
        List<String> whitelist = whitelistProperties.getEffectivePaths();
        log.debug("白名单路径列表：{}", whitelist);
        log.info("鉴权白名单检查：path={}", path);
        return whitelist.stream().anyMatch(pattern -> PATH_MATCHER.match(pattern, path));
    }
    
    /**
     * 从请求头中提取Token
     */
    private String extractToken(ServerHttpRequest request) {
        String authHeader = request.getHeaders().getFirst("Authorization");
        if (StringUtils.hasText(authHeader) && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7);
        }
        return null;
    }
    
    /**
     * 返回401未授权响应
     */
    private Mono<Void> unauthorized(ServerWebExchange exchange, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.UNAUTHORIZED);
        response.getHeaders().add("Content-Type", MediaType.APPLICATION_JSON_VALUE);
        
        try {
            Result<Object> result = Result.error(message);
            String body = objectMapper.writeValueAsString(result);
            DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
            return response.writeWith(Mono.just(buffer));
        } catch (Exception e) {
            log.error("序列化错误响应失败", e);
            try {
                // 使用 ObjectMapper 安全序列化 message，防止手动拼接 JSON 导致的注入风险
                String safeMessage = objectMapper.writeValueAsString(message);
                String body = "{\"code\": 401, \"msg\": " + safeMessage + "}";
                DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
                return response.writeWith(Mono.just(buffer));
            } catch (Exception ex) {
                // 极端情况下的降级处理
                String body = "{\"code\": 401, \"msg\": \"认证失败\"}";
                DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
                return response.writeWith(Mono.just(buffer));
            }
        }
    }
    
    @Override
    public int getOrder() {
        return FILTER_ORDER;
    }
}

