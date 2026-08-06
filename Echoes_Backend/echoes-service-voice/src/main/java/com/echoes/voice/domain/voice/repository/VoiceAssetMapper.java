package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.UUID;

/**
 * 音色资产 Mapper 接口
 * 
 * @author echoes
 */
@Mapper
public interface VoiceAssetMapper {

    /**
     * 根据ID查询音色资产
     *
     * @param voiceAssetId 音色资产ID
     * @return 音色资产，如果不存在则返回 null
     */
    VoiceAsset selectById(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 根据ID列表批量查询音色资产
     *
     * @param voiceAssetIds 音色资产ID列表
     * @return 音色资产列表
     */
    List<VoiceAsset> selectByIds(@Param("voiceAssetIds") List<UUID> voiceAssetIds);

    /**
     * 根据用户ID查询音色资产列表
     * 
     * @param userId 用户ID
     * @return 音色资产列表
     */
    List<VoiceAsset> selectByOwnerUserId(@Param("userId") UUID userId);

    /**
     * 根据用户ID和状态查询音色资产列表
     * 
     * @param userId 用户ID
     * @param status 状态
     * @return 音色资产列表
     */
    List<VoiceAsset> selectByUserIdAndStatus(@Param("userId") UUID userId, @Param("status") String status);

    /**
     * 根据用户ID和角色查询音色资产列表
     * 
     * @param userId 用户ID
     * @param role 角色
     * @return 音色资产列表
     */
    List<VoiceAsset> selectByUserIdAndRole(@Param("userId") UUID userId, @Param("role") String role);

    /**
     * 查询用户未删除的音色资产数量
     * 
     * @param userId 用户ID
     * @return 数量
     */
    int countByUserId(@Param("userId") UUID userId);

    /**
     * 插入音色资产
     * 
     * @param voiceAsset 音色资产实体
     * @return 影响的行数
     */
    int insert(VoiceAsset voiceAsset);

    /**
     * 更新音色资产
     * 
     * @param voiceAsset 音色资产实体
     * @return 影响的行数
     */
    int update(VoiceAsset voiceAsset);

    /**
     * 软删除音色资产
     * 
     * @param voiceAssetId 音色资产ID
     * @param deletedAt 删除时间
     * @return 影响的行数
     */
    int softDelete(@Param("voiceAssetId") UUID voiceAssetId, @Param("deletedAt") java.time.LocalDateTime deletedAt);

    /**
     * 更新外部voiceId
     * 
     * @param voiceAssetId 音色资产ID
     * @param voiceIdExternal 外部voiceId
     * @return 影响的行数
     */
    int updateVoiceIdExternal(@Param("voiceAssetId") UUID voiceAssetId, @Param("voiceIdExternal") String voiceIdExternal);

    /**
     * 更新状态
     * 
     * @param voiceAssetId 音色资产ID
     * @param status 状态
     * @return 影响的行数
     */
    int updateStatus(@Param("voiceAssetId") UUID voiceAssetId, @Param("status") String status);

    /**
     * 更新音色质量分
     *
     * @param voiceAssetId 音色资产ID
     * @param qualityScore 质量分
     * @return 影响行数
     */
    int updateQualityScore(@Param("voiceAssetId") UUID voiceAssetId, @Param("qualityScore") java.math.BigDecimal qualityScore);

    /**
     * 查询所有音色资产（管理端使用）
     *
     * @return 音色资产列表
     */
    List<VoiceAsset> selectAll();

    /**
     * 根据状态查询音色资产列表（管理端使用）
     *
     * @param status 状态
     * @return 音色资产列表
     */
    List<VoiceAsset> selectByStatus(@Param("status") String status);
}

