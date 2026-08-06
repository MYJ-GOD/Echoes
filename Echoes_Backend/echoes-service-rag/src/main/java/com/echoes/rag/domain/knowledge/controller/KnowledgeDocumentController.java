package com.echoes.rag.domain.knowledge.controller;

import com.echoes.rag.domain.knowledge.entity.KnowledgeChunk;
import com.echoes.rag.domain.knowledge.entity.KnowledgeDocument;
import com.echoes.rag.domain.knowledge.service.KnowledgeChunkService;
import com.echoes.rag.domain.knowledge.service.KnowledgeDocumentService;
import com.echoes.rag.domain.retrieval.engine.ChunkingStrategy;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;

/**
 * 知识文档管理 API
 */
@Slf4j
@RestController
@RequestMapping("/api/rag/knowledge-bases/{kbId}/documents")
@RequiredArgsConstructor
@Tag(name = "知识文档管理", description = "Knowledge Document Management API")
public class KnowledgeDocumentController {

    private final KnowledgeDocumentService documentService;
    private final KnowledgeChunkService chunkService;
    private final ChunkingStrategy chunkingStrategy;

    /**
     * 上传文档
     */
    @PostMapping
    @Operation(summary = "上传文档")
    public ResponseEntity<KnowledgeDocument> upload(
            @PathVariable String kbId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(required = false) String title,
            @RequestParam(defaultValue = "TEXT") String contentType
    ) throws IOException {
        log.info("Uploading document to kbId={}, filename={}", kbId, file.getOriginalFilename());

        // 生成文档 ID
        String docId = UUID.randomUUID().toString().replace("-", "");

        // 读取文件内容
        String content = new String(file.getBytes(), StandardCharsets.UTF_8);

        // 创建文档记录
        KnowledgeDocument document = new KnowledgeDocument();
        document.setDocId(docId);
        document.setKbId(kbId);
        document.setTitle(title != null ? title : file.getOriginalFilename());
        document.setContentType(contentType);
        document.setWordCount(content.length());

        // TODO: 存储文件到对象存储（OSS/本地）
        // document.setStorageKey(storageKey);

        documentService.create(document);

        // 同步分块（Phase 1 简化处理，实际应该异步）
        try {
            List<KnowledgeChunk> chunks = chunkingStrategy.chunk(content, docId, kbId);
            log.info("Document chunked: {} chunks created", chunks.size());

            // 保存到数据库
            chunkService.saveChunks(chunks);

            // 更新文档状态
            documentService.updateStatus(docId, "READY");
        } catch (Exception e) {
            log.error("Failed to chunk document", e);
            documentService.updateStatus(docId, "FAILED");
        }

        return ResponseEntity.ok(document);
    }

    /**
     * 查询文档列表
     */
    @GetMapping
    @Operation(summary = "查询文档列表")
    public ResponseEntity<List<KnowledgeDocument>> list(
            @PathVariable String kbId,
            @RequestParam(required = false) String status
    ) {
        List<KnowledgeDocument> documents = documentService.listByKb(kbId, status);
        return ResponseEntity.ok(documents);
    }

    /**
     * 删除文档
     */
    @DeleteMapping("/{docId}")
    @Operation(summary = "删除文档")
    public ResponseEntity<Void> delete(
            @PathVariable String kbId,
            @PathVariable String docId
    ) {
        // 删除 chunks
        chunkService.deleteByDoc(docId);
        // 删除文档记录
        documentService.removeById(docId);
        log.info("Deleted document: kbId={}, docId={}", kbId, docId);
        return ResponseEntity.ok().build();
    }

    /**
     * 查询文档片段
     */
    @GetMapping("/{docId}/chunks")
    @Operation(summary = "查询文档片段")
    public ResponseEntity<List<KnowledgeChunk>> getChunks(
            @PathVariable String kbId,
            @PathVariable String docId
    ) {
        List<KnowledgeChunk> chunks = chunkService.listByDoc(docId);
        return ResponseEntity.ok(chunks);
    }

    /**
     * 重新索引文档
     */
    @PostMapping("/{docId}/reindex")
    @Operation(summary = "重新索引文档")
    public ResponseEntity<Void> reindex(
            @PathVariable String kbId,
            @PathVariable String docId
    ) {
        // TODO: 重新分块并向量化
        log.info("Reindexing document: kbId={}, docId={}", kbId, docId);
        return ResponseEntity.ok().build();
    }
}
