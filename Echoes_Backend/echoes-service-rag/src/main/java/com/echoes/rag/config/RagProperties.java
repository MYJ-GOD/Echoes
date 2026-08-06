package com.echoes.rag.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * RAG 配置属性
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "rag")
public class RagProperties {

    /**
     * LangGraph 服务地址
     */
    private String langgraphUrl = "http://localhost:8088/api/v1";

    /**
     * Qdrant 配置
     */
    private QdrantProperties qdrant = new QdrantProperties();

    @Data
    public static class QdrantProperties {
        private String url = "http://localhost:6333";
        private String apiKey;
        private String collectionKnowledge = "knowledge_chunks";
        private String collectionConversation = "conversation_history";
        private int vectorSize = 1024;
        private int defaultTopK = 5;
        private double defaultThreshold = 0.5;
    }
}
