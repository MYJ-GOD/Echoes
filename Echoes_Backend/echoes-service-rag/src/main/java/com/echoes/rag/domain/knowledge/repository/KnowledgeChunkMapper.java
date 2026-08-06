package com.echoes.rag.domain.knowledge.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.echoes.rag.domain.knowledge.entity.KnowledgeChunk;
import org.apache.ibatis.annotations.Mapper;

/**
 * 知识片段 Mapper
 */
@Mapper
public interface KnowledgeChunkMapper extends BaseMapper<KnowledgeChunk> {

}
