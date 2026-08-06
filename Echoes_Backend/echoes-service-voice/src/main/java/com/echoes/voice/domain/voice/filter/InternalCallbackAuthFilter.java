package com.echoes.voice.domain.voice.filter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * AI回调接口认证过滤器
 * 验证内部AI服务的请求来源
 *
 * @author echoes
 */
@Slf4j
@Component
@Order(1)
public class InternalCallbackAuthFilter extends OncePerRequestFilter {

    private final ObjectMapper objectMapper;

    @Value("${echoes.voice.callback.internal-api-key:change-me-internal-callback-key}")
    private String expectedApiKey;

    @Value("${echoes.voice.callback.allowed-ips-internal:}")
    private String allowedIps;

    private static final String CALLBACK_PATH_PREFIX = "/internal/voice/callback";
    private static final String API_KEY_HEADER = "X-Internal-Api-Key";
    private static final String SOURCE_HEADER = "X-Internal-Source";

    public InternalCallbackAuthFilter() {
        this.objectMapper = new ObjectMapper();
        this.objectMapper.registerModule(new JavaTimeModule());
        this.objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String requestPath = request.getRequestURI();

        // 只对回调接口进行认证
        if (!requestPath.startsWith(CALLBACK_PATH_PREFIX)) {
            filterChain.doFilter(request, response);
            return;
        }

        // 1. 验证API Key
        String apiKey = request.getHeader(API_KEY_HEADER);
        if (apiKey == null || apiKey.isBlank()) {
            log.warn("AI回调认证失败: 缺少API Key, path={}", requestPath);
            sendErrorResponse(response, HttpServletResponse.SC_UNAUTHORIZED, "缺少认证信息");
            return;
        }

        if (!apiKey.equals(expectedApiKey)) {
            log.warn("AI回调认证失败: API Key不匹配, path={}", requestPath);
            sendErrorResponse(response, HttpServletResponse.SC_UNAUTHORIZED, "认证失败");
            return;
        }

        // 2. 验证来源
        String source = request.getHeader(SOURCE_HEADER);
        if (source == null || !source.equalsIgnoreCase("echoes-ai")) {
            log.warn("AI回调认证失败: 无效的来源, path={}, source={}", requestPath, source);
            sendErrorResponse(response, HttpServletResponse.SC_FORBIDDEN, "无效的请求来源");
            return;
        }

        // 3. 验证IP（如果配置了允许的IP列表）
        if (allowedIps != null && !allowedIps.isBlank()) {
            String clientIp = getClientIp(request);
            boolean ipAllowed = false;
            for (String allowedIp : allowedIps.split(",")) {
                if (allowedIp.trim().equals(clientIp) || matchesIpPattern(clientIp, allowedIp.trim())) {
                    ipAllowed = true;
                    break;
                }
            }
            if (!ipAllowed) {
                log.warn("AI回调认证失败: IP不在允许列表中, path={}, ip={}", requestPath, clientIp);
                sendErrorResponse(response, HttpServletResponse.SC_FORBIDDEN, "IP不受信任");
                return;
            }
        }

        log.debug("AI回调认证通过: path={}", requestPath);
        filterChain.doFilter(request, response);
    }

    /**
     * 发送错误响应
     */
    private void sendErrorResponse(HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType("application/json");

        Map<String, Object> error = new HashMap<>();
        error.put("code", status);
        error.put("message", message);

        response.getWriter().write(objectMapper.writeValueAsString(error));
    }

    /**
     * 获取客户端IP
     */
    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isBlank()) {
            return xForwardedFor.split(",")[0].trim();
        }

        String xRealIp = request.getHeader("X-Real-IP");
        if (xRealIp != null && !xRealIp.isBlank()) {
            return xRealIp;
        }

        return request.getRemoteAddr();
    }

    /**
     * 匹配IP模式（支持通配符）
     */
    private boolean matchesIpPattern(String ip, String pattern) {
        if (pattern.equals("*")) {
            return true;
        }

        if (pattern.contains("*")) {
            String regex = pattern.replace(".", "\\.").replace("*", "\\d{1,3}");
            return ip.matches(regex);
        }

        return ip.equals(pattern);
    }
}
