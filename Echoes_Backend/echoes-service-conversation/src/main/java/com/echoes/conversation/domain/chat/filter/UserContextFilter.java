package com.echoes.conversation.domain.chat.filter;

import com.echoes.context.BaseContext;
import com.echoes.utils.UuidUtils;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 用户上下文过滤器：从网关注入的 X-USER-ID 提取用户 ID 并设置到 BaseContext
 *
 * @author echoes
 */
@Component
@Slf4j
public class UserContextFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String userIdHeader = request.getHeader("X-USER-ID");
        String requestPath = request.getRequestURI();

        log.debug("UserContextFilter: path={}, X-USER-ID={}", requestPath, userIdHeader);

        if (userIdHeader != null && !userIdHeader.isBlank()) {
            try {
                java.util.UUID uid = UuidUtils.parseLenient(userIdHeader);
                BaseContext.setCurrentId(uid);
                log.debug("UserContextFilter: set userId={} for path={}", uid, requestPath);
            } catch (Exception e) {
                log.warn("UserContextFilter: failed to parse X-USER-ID='{}' for path={}, error={}",
                         userIdHeader, requestPath, e.getMessage());
                BaseContext.removeCurrentId();
            }
        } else {
            log.debug("UserContextFilter: X-USER-ID missing for path={}", requestPath);
        }

        try {
            filterChain.doFilter(request, response);
        } finally {
            BaseContext.removeCurrentId();
        }
    }
}
