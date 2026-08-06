package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.UserVoiceLink;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 用户与音色资产绑定关系 Mapper 接口
 */
@Mapper
public interface UserVoiceLinkMapper {

    /**
     * 插入绑定关系
     * 
     * @param userVoiceLink 绑定关系实体
     * @return 影响的行数
     */
    int insert(UserVoiceLink userVoiceLink);

    /**
     * 根据ID查询绑定关系
     * 
     * @param linkId 绑定关系ID
     * @return 绑定关系，如果不存在则返回 null
     */
    UserVoiceLink selectById(@Param("linkId") UUID linkId);

    /**
     * 根据用户ID和音色资产ID查询绑定关系
     * 
     * @param userId 用户ID
     * @param voiceAssetId 音色资产ID
     * @return 绑定关系，如果不存在则返回 null
     */
    UserVoiceLink selectByUserIdAndAssetId(@Param("userId") UUID userId, @Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 根据用户ID查询绑定关系列表
     * 
     * @param userId 用户ID
     * @return 绑定关系列表
     */
    List<UserVoiceLink> selectByUserId(@Param("userId") UUID userId);

    /**
     * 查询用户未删除的绑定关系
     * 
     * @param userId 用户ID
     * @return 绑定关系列表
     */
    List<UserVoiceLink> selectValidByUserId(@Param("userId") UUID userId);

    /**
     * 查询用户的默认音色绑定
     * 
     * @param userId 用户ID
     * @return 默认绑定关系，如果不存在则返回 null
     */
    UserVoiceLink selectDefaultByUserId(@Param("userId") UUID userId);

    /**
     * 查询用户指定角色的绑定
     * 
     * @param userId 用户ID
     * @param relationName 关系类型
     * @return 绑定关系列表
     */
    List<UserVoiceLink> selectByUserIdAndRelation(@Param("userId") UUID userId, @Param("relationName") String relationName);

    /**
     * 更新绑定关系
     * 
     * @param userVoiceLink 绑定关系实体
     * @return 影响的行数
     */
    int update(UserVoiceLink userVoiceLink);

    /**
     * 取消用户的默认音色设置
     * 
     * @param userId 用户ID
     * @return 影响的行数
     */
    int clearDefaultByUserId(@Param("userId") UUID userId);

    /**
     * 设置指定绑定为默认音色
     * 
     * @param linkId 绑定关系ID
     * @return 影响的行数
     */
    int setDefault(@Param("linkId") UUID linkId);

    /**
     * 软删除绑定关系
     * 
     * @param linkId 绑定关系ID
     * @param deletedAt 删除时间
     * @return 影响的行数
     */
    int softDelete(@Param("linkId") UUID linkId, @Param("deletedAt") LocalDateTime deletedAt);

    /**
     * 根据音色资产ID删除绑定关系
     * 
     * @param voiceAssetId 音色资产ID
     * @return 影响的行数
     */
    int deleteByVoiceAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 统计用户绑定数量
     * 
     * @param userId 用户ID
     * @return 数量
     */
    int countByUserId(@Param("userId") UUID userId);

    /**
     * 检查绑定是否已存在
     * 
     * @param userId 用户ID
     * @param voiceAssetId 音色资产ID
     * @return 数量
     */
    int countByUserIdAndAssetId(@Param("userId") UUID userId, @Param("voiceAssetId") UUID voiceAssetId);
}
