package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.VoiceTrainingTask;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

/**
 * 训练任务 Mapper 接口
 * 
 * @author echoes
 */
@Mapper
public interface VoiceTrainingTaskMapper {

    /**
     * 根据ID查询任务
     */
    VoiceTrainingTask selectById(@Param("taskId") UUID taskId);

    /**
     * 根据音色资产ID查询最新任务
     */
    VoiceTrainingTask selectLatestByVoiceAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 根据用户ID查询任务列表
     */
    List<VoiceTrainingTask> selectByUserId(@Param("userId") UUID userId);

    /**
     * 根据用户ID和状态查询任务列表
     */
    List<VoiceTrainingTask> selectByUserIdAndStatus(@Param("userId") UUID userId, @Param("status") String status);

    /**
     * 根据用户ID分页查询任务列表
     */
    List<VoiceTrainingTask> selectByUserIdWithPage(@Param("userId") UUID userId,
                                                     @Param("offset") int offset,
                                                     @Param("limit") int limit);

    /**
     * 根据用户ID和状态分页查询任务列表
     */
    List<VoiceTrainingTask> selectByUserIdAndStatusWithPage(@Param("userId") UUID userId,
                                                              @Param("status") String status,
                                                              @Param("offset") int offset,
                                                              @Param("limit") int limit);

    /**
     * 根据用户ID统计任务数量
     */
    int countByUserId(@Param("userId") UUID userId);

    /**
     * 根据用户ID和状态统计任务数量
     */
    int countByUserIdAndStatus(@Param("userId") UUID userId, @Param("status") String status);

    /**
     * 根据音色资产ID查询任务列表
     */
    List<VoiceTrainingTask> selectByVoiceAssetId(@Param("voiceAssetId") UUID voiceAssetId);

    /**
     * 查询进行中的任务
     */
    List<VoiceTrainingTask> selectRunningTasks();

    /**
     * 插入任务
     */
    int insert(VoiceTrainingTask task);

    /**
     * 更新进度
     */
    int updateProgress(@Param("taskId") UUID taskId, @Param("progress") BigDecimal progress);

    /**
     * 更新状态
     */
    int updateStatus(@Param("taskId") UUID taskId, @Param("status") String status);

    /**
     * 更新完成（成功或失败）
     */
    int updateComplete(@Param("taskId") UUID taskId, @Param("status") String status, 
                       @Param("endTime") LocalDateTime endTime, @Param("voiceModelId") UUID voiceModelId);

    /**
     * 更新日志路径
     */
    int updateLogPath(@Param("taskId") UUID taskId, @Param("logPath") String logPath);

    /**
     * 软删除
     */
    int softDelete(@Param("taskId") UUID taskId, @Param("deletedAt") LocalDateTime deletedAt);

    /**
     * 根据状态查询任务列表（管理端使用）
     *
     * @param status 状态
     * @return 任务列表
     */
    List<VoiceTrainingTask> selectByStatus(@Param("status") String status);

    /**
     * 查询所有任务（管理端使用，不包括已删除）
     *
     * @return 任务列表
     */
    List<VoiceTrainingTask> selectAll();
}

