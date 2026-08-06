package com.echoes.voice.domain.voice.service;

import com.echoes.voice.domain.voice.entity.dto.CreateGrantRequestDTO;
import com.echoes.voice.domain.voice.entity.po.VoiceGrant;

import java.util.List;
import java.util.UUID;

/**
 * 音色分享授权业务接口
 * 
 * @author echoes
 */
public interface IVoiceGrantService {

    /**
     * 创建分享授权
     * 
     * @param request 创建请求
     * @param userId 授权用户ID（所有者）
     * @return 授权VO
     */
    VoiceGrant createGrant(CreateGrantRequestDTO request, UUID userId);

    /**
     * 查询我给出的分享列表
     * 
     * @param userId 用户ID
     * @return 分享列表
     */
    List<VoiceGrant> listGivenGrants(UUID userId);

    /**
     * 查询我收到的分享列表
     * 
     * @param userId 用户ID
     * @return 分享列表
     */
    List<VoiceGrant> listReceivedGrants(UUID userId);

    /**
     * 取消分享
     * 
     * @param grantId 授权ID
     * @param userId 用户ID（只有所有者可以取消）
     */
    void revokeGrant(UUID grantId, UUID userId);

    /**
     * 检查用户是否有权限使用音色
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     * @return true-有权限
     */
    boolean hasPermission(UUID voiceAssetId, UUID userId);
}

