package com.echoes.rag.domain.knowledge.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.echoes.rag.domain.knowledge.entity.KnowledgeDocument;
import org.apache.ibatis.annotations.Mapper;

/**
 * 知识文档 Mapper
 */
@Mapper
public interface KnowledgeDocumentMapper extends BaseMapper<KnowledgeDocument> {

}
