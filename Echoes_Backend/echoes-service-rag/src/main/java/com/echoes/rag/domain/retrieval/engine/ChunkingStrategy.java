package com.echoes.rag.domain.retrieval.engine;

import com.echoes.rag.domain.knowledge.entity.KnowledgeChunk;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 文档分块策略
 *
 * 支持多种分块方式：
 * 1. 按段落分块（适合 Markdown/文本）
 * 2. 按固定字符数分块（适合长文本）
 * 3. 按语义分块（需要 NLP 模型，暂不实现）
 */
@Slf4j
@Component
public class ChunkingStrategy {

    /**
     * 默认分块大小（字符数）
     */
    private static final int DEFAULT_CHUNK_SIZE = 500;

    /**
     * 重叠大小（字符数）
     */
    private static final int DEFAULT_OVERLAP_SIZE = 100;

    /**
     * 对文档内容进行分块
     *
     * @param content 文档内容
     * @param docId 文档 ID
     * @param kbId 知识库 ID
     * @return 分块列表
     */
    public List<KnowledgeChunk> chunk(String content, String docId, String kbId) {
        log.info("Chunking document: docId={}, contentLength={}", docId, content.length());

        // 首先尝试按段落分块
        List<String> chunks = chunkByParagraph(content);

        // 如果段落太大，进一步拆分
        List<String> finalChunks = new ArrayList<>();
        for (String chunk : chunks) {
            if (chunk.length() > DEFAULT_CHUNK_SIZE * 2) {
                finalChunks.addAll(chunkBySize(chunk));
            } else {
                finalChunks.add(chunk);
            }
        }

        // 转换为 KnowledgeChunk 实体
        List<KnowledgeChunk> result = new ArrayList<>();
        for (int i = 0; i < finalChunks.size(); i++) {
            KnowledgeChunk kc = new KnowledgeChunk();
            kc.setChunkId(generateChunkId(docId, i));
            kc.setDocId(docId);
            kc.setKbId(kbId);
            kc.setChunkIndex(i);
            kc.setContent(finalChunks.get(i));
            result.add(kc);
        }

        log.info("Chunking completed: {} chunks created", result.size());
        return result;
    }

    /**
     * 按段落分块
     */
    private List<String> chunkByParagraph(String content) {
        List<String> chunks = new ArrayList<>();

        // 按双换行符分割段落
        String[] paragraphs = content.split("\\n\\s*\\n");

        StringBuilder currentChunk = new StringBuilder();
        for (String para : paragraphs) {
            String trimmed = para.trim();
            if (trimmed.isEmpty()) {
                continue;
            }

            if (currentChunk.length() + trimmed.length() > DEFAULT_CHUNK_SIZE) {
                if (currentChunk.length() > 0) {
                    chunks.add(currentChunk.toString());
                    currentChunk = new StringBuilder();
                }

                // 如果单个段落超过大小，使用固定大小分块
                if (trimmed.length() > DEFAULT_CHUNK_SIZE) {
                    chunks.addAll(chunkBySize(trimmed));
                } else {
                    currentChunk.append(trimmed);
                }
            } else {
                if (currentChunk.length() > 0) {
                    currentChunk.append("\n\n");
                }
                currentChunk.append(trimmed);
            }
        }

        if (currentChunk.length() > 0) {
            chunks.add(currentChunk.toString());
        }

        return chunks;
    }

    /**
     * 按固定大小分块（带重叠）
     */
    private List<String> chunkBySize(String content) {
        List<String> chunks = new ArrayList<>();
        int start = 0;

        while (start < content.length()) {
            int end = Math.min(start + DEFAULT_CHUNK_SIZE, content.length());

            // 尝试在句子边界处切分
            if (end < content.length()) {
                int lastPeriod = content.lastIndexOf('.', end);
                int lastQuestion = content.lastIndexOf('?', end);
                int lastExclaim = content.lastIndexOf('!', end);
                int lastNewline = content.lastIndexOf('\n', end);

                int splitPoint = Math.max(
                    Math.max(lastPeriod, lastQuestion),
                    Math.max(lastExclaim, lastNewline)
                );

                if (splitPoint > start + DEFAULT_CHUNK_SIZE / 2) {
                    end = splitPoint + 1;
                }
            }

            String chunk = content.substring(start, end).trim();
            if (!chunk.isEmpty()) {
                chunks.add(chunk);
            }

            // 移动起始位置（带重叠）
            start = end - DEFAULT_OVERLAP_SIZE;
            if (start < 0) {
                start = end;
            }
        }

        return chunks;
    }

    /**
     * 生成 Chunk ID
     */
    private String generateChunkId(String docId, int index) {
        return docId + "_chunk_" + index;
    }
}
