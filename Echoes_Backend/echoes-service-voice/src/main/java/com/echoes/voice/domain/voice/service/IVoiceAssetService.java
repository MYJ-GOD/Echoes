package com.echoes.voice.domain.voice.service;

import com.echoes.voice.domain.voice.entity.dto.CreateVoiceAssetRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.UpdateVoiceAssetRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.VoiceAssetQueryDTO;
import com.echoes.voice.domain.voice.entity.vo.VoiceAssetVO;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;

import java.util.List;
import java.util.UUID;

/**
 * 音色资产业务接口
 * 
 * @author echoes
 */
public interface IVoiceAssetService {

    /**
     * 创建音色资产
     * 1. 验证ref音频
     * 2. 创建voice_asset记录
     * 3. 创建voice_training_task（异步训练）
     * 4. 返回voiceAssetId
     * 
     * @param request 创建请求
     * @param userId 用户ID
     * @return 音色资产VO
     */
    VoiceAssetVO createVoiceAsset(CreateVoiceAssetRequestDTO request, UUID userId);

    /**
     * 查询用户音色列表
     * 
     * @param userId 用户ID
     * @param query 查询条件
     * @return 分页结果
     */
    Page<VoiceAssetVO> listUserVoices(UUID userId, VoiceAssetQueryDTO query);

    /**
     * 获取音色详情
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID (用于权限校验)
     * @return 音色资产VO
     */
    VoiceAssetVO getVoiceAsset(UUID voiceAssetId, UUID userId);

    /**
     * 更新音色信息
     * 
     * @param voiceAssetId 音色资产ID
     * @param request 更新请求
     * @param userId 用户ID
     * @return 更新后的音色资产VO
     */
    VoiceAssetVO updateVoiceAsset(UUID voiceAssetId, UpdateVoiceAssetRequestDTO request, UUID userId);

    /**
     * 删除音色（软删除）
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     */
    void deleteVoiceAsset(UUID voiceAssetId, UUID userId);

    /**
     * 设置默认音色
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     */
    void setDefaultVoice(UUID voiceAssetId, UUID userId);

    /**
     * 检查用户是否有权限访问音色
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     * @return true-有权限, false-无权限
     */
    boolean hasAccessPermission(UUID voiceAssetId, UUID userId);

    /**
     * 检查用户是否是音色所有者
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     * @return true-是所有者, false-不是
     */
    boolean isOwner(UUID voiceAssetId, UUID userId);

    /**
     * 获取可用音色列表（自己的 + 收到的分享）
     * 
     * @param userId 用户ID
     * @return 可用的音色列表
     */
    List<VoiceAssetVO> getAvailableVoices(UUID userId);
}

