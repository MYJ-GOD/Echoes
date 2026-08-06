package com.echoes.rag.domain.knowledge.service;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.echoes.rag.domain.knowledge.entity.KnowledgeDocument;
import com.echoes.rag.domain.knowledge.repository.KnowledgeDocumentMapper;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 知识文档服务
 */
@Service
public class KnowledgeDocumentService extends ServiceImpl<KnowledgeDocumentMapper, KnowledgeDocument> {

    /**
     * 查询知识库下的文档列表
     */
    public List<KnowledgeDocument> listByKb(String kbId, String status) {
        return lambdaQuery()
                .eq(KnowledgeDocument::getKbId, kbId)
                .eq(status != null, KnowledgeDocument::getStatus, status)
                .orderByDesc(KnowledgeDocument::getCreateTime)
                .list();
    }

    /**
     * 创建文档
     */
    public KnowledgeDocument create(KnowledgeDocument document) {
        document.setStatus("PENDING");
        save(document);
        return document;
    }

    /**
     * 更新文档状态
     */
    public void updateStatus(String docId, String status) {
        lambdaUpdate()
                .eq(KnowledgeDocument::getDocId, docId)
                .set(KnowledgeDocument::getStatus, status)
                .update();
    }
}
