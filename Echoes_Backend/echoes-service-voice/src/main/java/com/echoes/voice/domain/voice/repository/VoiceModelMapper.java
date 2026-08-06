package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.VoiceModel;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.UUID;

/**
 * 声纹模型 Mapper 接口
 */
@Mapper
public interface VoiceModelMapper {

    /**
     * 根据用户ID和音色名称查询最新成功模型
     */
    VoiceModel selectByUserIdAndVoiceName(@Param("userId") UUID userId, @Param("voiceName") String voiceName);

    /**
     * 插入声纹模型
     */
    int insert(VoiceModel voiceModel);

    /**
     * 更新声纹模型
     */
    int update(VoiceModel voiceModel);

    /**
     * 根据模型ID查询
     */
    VoiceModel selectById(@Param("voiceModelId") UUID voiceModelId);

    /**
     * 根据用户ID查询模型列表
     */
    List<VoiceModel> selectByUserId(@Param("userId") UUID userId);

    /**
     * 查询某个音色资产当前最大模型版本号
     */
    Integer selectMaxModelVersionByAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 查询某个音色资产最新成功的模型（具有最高版本号）
     */
    VoiceModel selectLatestSuccessByAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 根据音色资产 ID 查询模型列表（按创建时间排序）
     *
     * @param voiceAssetId 音色资产 ID
     * @return 模型列表
     */
    List<VoiceModel> selectByAssetId(@Param("voiceAssetId") UUID voiceAssetId);
}
