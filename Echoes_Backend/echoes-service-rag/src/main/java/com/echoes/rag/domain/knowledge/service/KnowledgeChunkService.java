package com.echoes.rag.domain.knowledge.service;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.echoes.rag.domain.knowledge.entity.KnowledgeChunk;
import com.echoes.rag.domain.knowledge.repository.KnowledgeChunkMapper;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 知识片段服务
 */
@Service
public class KnowledgeChunkService extends ServiceImpl<KnowledgeChunkMapper, KnowledgeChunk> {

    /**
     * 查询文档的片段列表
     */
    public List<KnowledgeChunk> listByDoc(String docId) {
        return lambdaQuery()
                .eq(KnowledgeChunk::getDocId, docId)
                .orderByAsc(KnowledgeChunk::getChunkIndex)
                .list();
    }

    /**
     * 查询知识库的片段
     */
    public List<KnowledgeChunk> listByKb(String kbId, int limit) {
        return lambdaQuery()
                .eq(KnowledgeChunk::getKbId, kbId)
                .last("LIMIT " + limit)
                .list();
    }

    /**
     * 保存片段列表
     */
    public void saveChunks(List<KnowledgeChunk> chunks) {
        if (chunks != null && !chunks.isEmpty()) {
            saveBatch(chunks);
        }
    }

    /**
     * 删除文档的所有片段
     */
    public void deleteByDoc(String docId) {
        lambdaUpdate()
                .eq(KnowledgeChunk::getDocId, docId)
                .remove();
    }

    /**
     * 更新片段的向量 ID
     */
    public void updateVectorId(String chunkId, String vectorId) {
        lambdaUpdate()
                .eq(KnowledgeChunk::getChunkId, chunkId)
                .set(KnowledgeChunk::getVectorId, vectorId)
                .update();
    }
}
