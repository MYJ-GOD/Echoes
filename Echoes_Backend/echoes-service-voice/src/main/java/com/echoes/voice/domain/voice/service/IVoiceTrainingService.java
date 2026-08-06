package com.echoes.voice.domain.voice.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.echoes.voice.domain.voice.entity.dto.CreateTrainingTaskRequestDTO;
import com.echoes.voice.domain.voice.entity.vo.TrainingTaskVO;

import java.util.UUID;

/**
 * 训练任务业务接口
 * 
 * @author echoes
 */
public interface IVoiceTrainingService {

    /**
     * 创建训练任务
     * 1. 验证音色资产
     * 2. 创建训练任务记录
     * 3. 发送训练消息到消息队列
     * 4. 返回taskId
     * 
     * @param request 创建请求
     * @param userId 用户ID
     * @return 任务VO
     */
    TrainingTaskVO createTrainingTask(CreateTrainingTaskRequestDTO request, UUID userId);

    /**
     * 查询任务详情
     * 
     * @param taskId 任务ID
     * @param userId 用户ID
     * @return 任务VO
     */
    TrainingTaskVO getTask(UUID taskId, UUID userId);

    /**
     * 查询用户任务列表
     * 
     * @param userId 用户ID
     * @param status 状态筛选
     * @param pageNum 页码
     * @param pageSize 每页数量
     * @return 分页结果
     */
    Page<TrainingTaskVO> listUserTasks(UUID userId, String status, int pageNum, int pageSize);

    /**
     * 查询音色资产的任务列表
     * 
     * @param voiceAssetId 音色资产ID
     * @param userId 用户ID
     * @return 任务列表
     */
    java.util.List<TrainingTaskVO> listAssetTasks(UUID voiceAssetId, UUID userId);

    /**
     * 取消训练任务
     * 
     * @param taskId 任务ID
     * @param userId 用户ID
     */
    void cancelTask(UUID taskId, UUID userId);

    /**
     * AI回调 - 更新任务进度
     * 
     * @param taskId 任务ID
     * @param progress 进度 (0-100)
     */
    void updateProgress(UUID taskId, java.math.BigDecimal progress);

    /**
     * AI回调 - 任务完成（成功）
     *
     * @param taskId 任务ID
     * @param voiceModelId 生成的模型ID
     * @param voiceIdExternal 外部voiceId
     * @param similarityScore 相似度评分
     * @param modelPath 模型在OSS中的存储路径
     */
    void completeSuccess(UUID taskId, UUID voiceModelId, String voiceIdExternal, java.math.BigDecimal similarityScore, String modelPath);

    /**
     * AI回调 - 任务失败
     * 
     * @param taskId 任务ID
     * @param errorMessage 错误信息
     */
    void completeFailed(UUID taskId, String errorMessage);

    /**
     * 获取训练测试音频
     * 根据 voiceModelId 查询对应的测试音频文件路径
     *
     * @param voiceModelId 声纹模型ID
     * @param userId 用户ID
     * @return 测试音频文件路径
     */
    String getTestAudioPath(UUID voiceModelId, UUID userId);

    /**
     * 重试训练任务
     * 基于失败的任务创建一个新的训练任务
     *
     * @param taskId 原任务ID
     * @param userId 用户ID
     * @param request 重试请求（可选参数）
     * @return 新创建的任务VO
     */
    TrainingTaskVO retryTask(UUID taskId, UUID userId, CreateTrainingTaskRequestDTO request);
}

