package com.echoes.voice.domain.voice.filter;

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

@Component
@Slf4j
public class UserContextFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        String userIdHeader = request.getHeader("X-USER-ID");
        String requestPath = request.getRequestURI();
        String voiceName = request.getParameter("voiceName");

        log.debug("event=user_context_check stage=incoming path={} voiceName={} xUserIdHeader={}",
                requestPath, voiceName, userIdHeader);

        if ("/internal/voice/inference/synthesize-stream".equals(requestPath)
                && (userIdHeader == null || userIdHeader.isBlank())) {
            log.warn("event=user_context_check validationResult=rejected reason=missing_header path={} voiceName={} xUserIdHeader={}",
                    requestPath, voiceName, userIdHeader);
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":\"MISSING_USER_ID\",\"message\":\"X-USER-ID is required\"}");
            return;
        }

        if (userIdHeader != null && !userIdHeader.isBlank()) {
            try {
                java.util.UUID uid = UuidUtils.parseLenient(userIdHeader);
                BaseContext.setCurrentId(uid);
                log.info("event=user_context_check validationResult=accepted path={} voiceName={} resolvedUserId={}",
                        requestPath, voiceName, uid);
            } catch (Exception e) {
                log.warn("event=user_context_check validationResult=parse_failed path={} voiceName={} xUserIdHeader={} parseError={}",
                        requestPath, voiceName, userIdHeader, e.getMessage());
                BaseContext.removeCurrentId();
            }
        } else {
            log.debug("event=user_context_check validationResult=missing path={} voiceName={} xUserIdHeader={}",
                    requestPath, voiceName, userIdHeader);
        }

        try {
            filterChain.doFilter(request, response);
        } finally {
            BaseContext.removeCurrentId();
        }
    }
}
