package com.echoes.admin.domain.governance.repository;

import com.echoes.admin.domain.governance.entity.vo.AuditEventVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 审计事件 Mapper
 */
@Mapper
public interface AuditEventMapper {

    /**
     * 分页查询审计事件
     */
    List<AuditEventVO> selectAuditEvents(
            @Param("traceId") String traceId,
            @Param("sessionId") String sessionId,
            @Param("turnId") String turnId,
            @Param("userId") UUID userId,
            @Param("voiceAssetId") UUID voiceAssetId,
            @Param("action") String action,
            @Param("result") String result,
            @Param("timeFrom") LocalDateTime timeFrom,
            @Param("timeTo") LocalDateTime timeTo,
            @Param("offset") Integer offset,
            @Param("limit") Integer limit
    );

    /**
     * 查询审计事件总数
     */
    int countAuditEvents(
            @Param("traceId") String traceId,
            @Param("sessionId") String sessionId,
            @Param("turnId") String turnId,
            @Param("userId") UUID userId,
            @Param("voiceAssetId") UUID voiceAssetId,
            @Param("action") String action,
            @Param("result") String result,
            @Param("timeFrom") LocalDateTime timeFrom,
            @Param("timeTo") LocalDateTime timeTo
    );

    /**
     * 根据 ID 查询审计事件
     */
    AuditEventVO selectAuditEventById(@Param("auditId") UUID auditId);
}
