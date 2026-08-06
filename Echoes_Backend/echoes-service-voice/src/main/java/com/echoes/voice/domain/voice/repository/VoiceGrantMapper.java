package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.VoiceGrant;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 音色授权 Mapper 接口
 */
@Mapper
public interface VoiceGrantMapper {

    VoiceGrant selectById(@Param("grantId") UUID grantId);

    List<VoiceGrant> selectByVoiceAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    List<VoiceGrant> selectByGranteeUserId(@Param("granteeUserId") UUID granteeUserId);

    List<VoiceGrant> selectValidGrantsByUserId(@Param("granteeUserId") UUID granteeUserId, @Param("now") LocalDateTime now);

    int countByAssetAndGrantee(@Param("voiceAssetId") UUID voiceAssetId, @Param("granteeUserId") UUID granteeUserId, @Param("permission") String permission);

    int insert(VoiceGrant voiceGrant);

    int update(VoiceGrant voiceGrant);

    int deleteById(@Param("grantId") UUID grantId);

    int deleteByVoiceAssetId(@Param("voiceAssetId") UUID voiceAssetId);
}

