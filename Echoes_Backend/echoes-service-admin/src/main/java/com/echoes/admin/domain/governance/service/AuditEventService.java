package com.echoes.admin.domain.governance.service;

import com.echoes.admin.domain.governance.entity.dto.AuditQueryDTO;
import com.echoes.admin.domain.governance.entity.vo.AuditEventVO;
import com.echoes.admin.domain.governance.repository.AuditEventMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 审计事件服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditEventService {

    private final AuditEventMapper auditEventMapper;

    /**
     * 分页查询审计事件
     */
    public List<AuditEventVO> listAuditEvents(AuditQueryDTO query) {
        int offset = (query.getPage() - 1) * query.getSize();
        return auditEventMapper.selectAuditEvents(
                query.getTraceId(),
                query.getSessionId(),
                query.getTurnId(),
                parseUuid(query.getUserId()),
                parseUuid(query.getVoiceAssetId()),
                query.getAction(),
                query.getResult(),
                query.getTimeFrom(),
                query.getTimeTo(),
                offset,
                query.getSize()
        );
    }

    /**
     * 查询审计事件总数
     */
    public int countAuditEvents(AuditQueryDTO query) {
        return auditEventMapper.countAuditEvents(
                query.getTraceId(),
                query.getSessionId(),
                query.getTurnId(),
                parseUuid(query.getUserId()),
                parseUuid(query.getVoiceAssetId()),
                query.getAction(),
                query.getResult(),
                query.getTimeFrom(),
                query.getTimeTo()
        );
    }

    /**
     * 根据 ID 查询审计事件
     */
    public AuditEventVO getAuditEventById(String auditId) {
        return auditEventMapper.selectAuditEventById(parseUuid(auditId));
    }

    private java.util.UUID parseUuid(String idStr) {
        if (idStr == null || idStr.isBlank()) {
            return null;
        }
        try {
            return com.echoes.utils.UuidUtils.parseLenient(idStr);
        } catch (Exception e) {
            return null;
        }
    }
}
