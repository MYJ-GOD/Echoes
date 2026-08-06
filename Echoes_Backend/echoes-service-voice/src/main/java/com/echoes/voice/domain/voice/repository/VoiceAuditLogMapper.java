package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.VoiceAuditLog;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 审计日志 Mapper 接口
 * 
 * @author echoes
 */
@Mapper
public interface VoiceAuditLogMapper {

    /**
     * 根据ID查询审计日志
     * 
     * @param auditId 审计ID
     * @return 审计日志，如果不存在则返回 null
     */
    VoiceAuditLog selectById(@Param("auditId") UUID auditId);

    /**
     * 根据音色资产ID查询审计日志列表
     * 
     * @param voiceAssetId 音色资产ID
     * @return 审计日志列表
     */
    List<VoiceAuditLog> selectByVoiceAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 根据操作用户ID查询审计日志列表
     * 
     * @param actorUserId 操作用户ID
     * @return 审计日志列表
     */
    List<VoiceAuditLog> selectByActorUserId(@Param("actorUserId") UUID actorUserId);

    /**
     * 根据音色资产ID和用户ID查询审计日志
     * 
     * @param voiceAssetId 音色资产ID
     * @param actorUserId 操作用户ID
     * @param limit 限制数量
     * @return 审计日志列表
     */
    List<VoiceAuditLog> selectByAssetAndActor(
            @Param("voiceAssetId") UUID voiceAssetId,
            @Param("actorUserId") UUID actorUserId,
            @Param("limit") int limit);

    /**
     * 插入审计日志
     * 
     * @param auditLog 审计日志实体
     * @return 影响的行数
     */
    int insert(VoiceAuditLog auditLog);

    /**
     * 清理过期审计日志（保留90天）
     * 
     * @param cutoffDate 截止日期
     * @return 删除的行数
     */
    int deleteOlderThan(@Param("cutoffDate") LocalDateTime cutoffDate);
}

