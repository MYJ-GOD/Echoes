package com.echoes.voice.domain.voice.repository;

import com.echoes.voice.domain.voice.entity.po.VoiceRef;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

/**
 * 原始音频引用 Mapper 接口
 * 
 * @author echoes
 */
@Mapper
public interface VoiceRefMapper {

    /**
     * 根据refId查询
     * 
     * @param refId 引用ID
     * @return 音频引用，如果不存在则返回 null
     */
    VoiceRef selectById(@Param("refId") String refId);

    /**
     * 查询 storageKey (用于训练时下载音频)
     * 
     * @param refId 引用ID
     * @return storageKey，如果不存在则返回 null
     */
    String selectStorageKeyById(@Param("refId") String refId);

    /**
     * 检查引用是否存在且未过期
     * 
     * @param refId 引用ID
     * @return 数量
     */
    int countValidById(@Param("refId") String refId);

    /**
     * 插入 voice_ref 记录
     *
     * @param voiceRef 引用实体
     * @return 影响行数
     */
    int insert(VoiceRef voiceRef);
}

