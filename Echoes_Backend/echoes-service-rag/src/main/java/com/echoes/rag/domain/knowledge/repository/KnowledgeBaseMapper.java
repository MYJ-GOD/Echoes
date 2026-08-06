package com.echoes.rag.domain.knowledge.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.echoes.rag.domain.knowledge.entity.KnowledgeBase;
import org.apache.ibatis.annotations.Mapper;

/**
 * 知识库 Mapper
 */
@Mapper
public interface KnowledgeBaseMapper extends BaseMapper<KnowledgeBase> {

}
