package com.echoes.conversation.domain.chat.client;

import com.echoes.conversation.common.constants.ErrorCode;
import com.echoes.conversation.common.constants.AIChatConstants;
import com.echoes.exception.BusinessException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 阿里云百炼 (DashScope) AI 客户端
 * 使用 Spring AI Alibaba 替换 ChatGLM，提供兼容 OpenAI 的接口格式。
 */
@Slf4j
@Service
public class DashScopeAiClient {

    private final ChatModel chatModel;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public DashScopeAiClient(@Qualifier("QWen") ChatModel chatModel) {
        this.chatModel = chatModel;
    }

    // ===== 配置常量 =====
    private static final String MODEL_NAME = "qwen-turbo";
    private static final String REQUEST_ID_PREFIX = "chatcmpl-";
    private static final String OBJECT_COMPLETION = "chat.completion";
    private static final String OBJECT_COMPLETION_CHUNK = "chat.completion.chunk";
    private static final String DONE_DATA = "data: [DONE]\n\n";

    // 默认生成参数
    private static final double DEFAULT_TEMPERATURE = 0.7;
    private static final double DEFAULT_TOP_P = 0.9;
    private static final int DEFAULT_MAX_TOKENS = 1024;

    /**
     * 非流式对话（同步）
     */
    public JsonNode chat(List<com.echoes.conversation.domain.chat.entity.dto.MessageDTO> messages,
                         Double temperature,
                         Double topP,
                         Integer maxTokens) {
        try {
            List<Message> springMessages = convertToSpringMessages(messages);
            String requestId = REQUEST_ID_PREFIX + System.currentTimeMillis();
            long createdTime = System.currentTimeMillis() / 1000;

            log.debug("[{}] 发送非流式请求，消息数: {}", requestId, springMessages.size());

            Prompt prompt = new Prompt(springMessages);
            ChatResponse response = chatModel.call(prompt);
            try {
                log.debug("DashScope.chat - raw ChatResponse: {}", response == null ? "null" : response.toString());
            } catch (Exception e) {
                log.debug("DashScope.chat - failed to log raw response: {}", e.getMessage());
            }

            AssistantMessage assistantMessage = response.getResult().getOutput();
            String content = extractContentFromAssistantMessage(assistantMessage);
            Map<String, Object> usage = calculateUsage(messages, content);

            return buildCompletionJson(requestId, createdTime, content, "stop", usage);
        } catch (Exception e) {
            log.error("DashScope 同步调用失败", e);
            throw new BusinessException(ErrorCode.SERVICE_UNAVAILABLE.getCode(),
                    "DashScope 服务不可用: " + e.getMessage());
        }
    }

    /**
     * 非流式对话（异步包装）
     * 注意：底层可能仍为阻塞调用，此处仅为响应式封装
     */
    public Mono<JsonNode> chatAsync(List<com.echoes.conversation.domain.chat.entity.dto.MessageDTO> messages,
                                    Double temperature,
                                    Double topP,
                                    Integer maxTokens) {
        return Mono.fromCallable(() -> chat(messages, temperature, topP, maxTokens))
                .doOnError(e -> log.error("DashScope 异步请求失败", e))
                .onErrorMap(e -> new BusinessException(ErrorCode.SERVICE_UNAVAILABLE.getCode(),
                        "DashScope 服务不可用: " + e.getMessage()));
    }

    /**
     * 流式对话（SSE 格式输出）
     */
    public Flux<String> chatStream(List<com.echoes.conversation.domain.chat.entity.dto.MessageDTO> messages,
                                   Double temperature,
                                   Double topP,
                                   Integer maxTokens) {
        List<Message> springMessages = convertToSpringMessages(messages);
        String requestId = REQUEST_ID_PREFIX + System.currentTimeMillis();
        long createdTime = System.currentTimeMillis() / 1000;

        log.debug("[{}] 发送流式请求，消息数: {}", requestId, springMessages.size());

        Prompt prompt = new Prompt(springMessages);
        Flux<ChatResponse> responseFlux = chatModel.stream(prompt);

        return responseFlux
                .map(resp -> {
                    AssistantMessage assistantMessage = resp.getResult().getOutput();
                    try {
                        log.debug("DashScope.chatStream - AssistantMessage: {}", assistantMessage == null ? "null" : assistantMessage.toString());
                    } catch (Exception e) {
                        log.debug("DashScope.chatStream - failed to log assistantMessage: {}", e.getMessage());
                    }
                    String content = extractContentFromAssistantMessage(assistantMessage);
                    if (content == null || content.isEmpty()) {
                        return "";
                    }
                    return formatSSEChunk(requestId, createdTime, content);
                })
                .concatWith(Mono.just(DONE_DATA))
                .doOnComplete(() -> log.debug("[{}] 流式响应完成", requestId))
                .doOnError(e -> log.error("[{}] 流式响应失败", requestId, e));
    }

    /**
     * 简单问答（支持自定义参数）
     */
    public String simpleChat(String userMessage) {
        return simpleChat(userMessage, DEFAULT_TEMPERATURE, DEFAULT_TOP_P, DEFAULT_MAX_TOKENS);
    }

    public String simpleChat(String userMessage, double temperature, double topP, int maxTokens) {
        // 确保包含系统提示词，禁止表情符号
        List<com.echoes.conversation.domain.chat.entity.dto.MessageDTO> messages = new ArrayList<>();
        messages.add(new com.echoes.conversation.domain.chat.entity.dto.MessageDTO("system", AIChatConstants.SYSTEM_PROMPT));
        messages.add(new com.echoes.conversation.domain.chat.entity.dto.MessageDTO("user", userMessage));

        JsonNode response = chat(messages, temperature, topP, maxTokens);
        return extractContentFromResponse(response);
    }

    /**
     * 获取模型列表（模拟 OpenAI 格式）
     */
    public JsonNode listModels() {
        Map<String, Object> data = new HashMap<>();
        data.put("id", MODEL_NAME);
        data.put("object", "model");
        data.put("created", System.currentTimeMillis() / 1000);
        data.put("owned_by", "dashscope");

        List<Map<String, Object>> modelList = Collections.singletonList(data);
        Map<String, Object> result = new HashMap<>();
        result.put("object", "list");
        result.put("data", modelList);

        return objectMapper.valueToTree(result);
    }

    // ===== 内部工具方法 =====

    /**
     * 从 AssistantMessage 中提取文本内容
     * TODO(#CONVERSATION-201): 依赖下载完成后，根据 DashScope SDK 实际 API 调整此方法
     * 当前使用反射方式兼容不同版本的 SDK
     */
    private String extractContentFromAssistantMessage(AssistantMessage message) {
        // 尝试多种可能的方法名
        try {
            log.debug("extractContentFromAssistantMessage - message class: {}, toString: {}",
                    message == null ? "null" : message.getClass().getName(),
                    message == null ? "null" : message.toString());
        } catch (Exception e) {
            log.debug("extractContentFromAssistantMessage - failed to log message: {}", e.getMessage());
        }
        try {
            // 方法1: getContent()
            try {
                java.lang.reflect.Method method = message.getClass().getMethod("getContent");
                Object result = method.invoke(message);
                if (result != null) {
                    return result.toString();
                }
            } catch (NoSuchMethodException e) {
                // 继续尝试其他方法
            }

            // 方法2: getText()
            try {
                java.lang.reflect.Method method = message.getClass().getMethod("getText");
                Object result = method.invoke(message);
                if (result != null) {
                    return result.toString();
                }
            } catch (NoSuchMethodException e) {
                // 继续尝试其他方法
            }

            // 方法3: getContents() 然后获取第一个
            try {
                java.lang.reflect.Method method = message.getClass().getMethod("getContents");
                Object result = method.invoke(message);
                if (result instanceof java.util.Collection) {
                    java.util.Collection<?> contents = (java.util.Collection<?>) result;
                    if (!contents.isEmpty()) {
                        Object first = contents.iterator().next();
                        // 尝试从 Content 对象获取文本
                        try {
                            java.lang.reflect.Method getTextMethod = first.getClass().getMethod("getText");
                            return getTextMethod.invoke(first).toString();
                        } catch (Exception e) {
                            return first.toString();
                        }
                    }
                }
            } catch (NoSuchMethodException e) {
                // 继续尝试其他方法
            }
        } catch (Exception e) {
            log.warn("提取 AssistantMessage 内容失败，使用 toString()", e);
        }

        // 最后尝试：toString()
        return message.toString();
    }

    /**
     * 转换为 Spring AI Message 列表
     * 如果消息列表中没有系统提示词，自动添加
     */
    private List<Message> convertToSpringMessages(List<com.echoes.conversation.domain.chat.entity.dto.MessageDTO> messages) {
        // 检查是否已有系统提示词
        boolean hasSystemMessage = messages.stream()
                .anyMatch(msg -> "system".equals(msg.getRole()));

        List<Message> springMessages = new ArrayList<>();

        // 如果没有系统消息，自动添加系统提示词（禁止表情符号）
        if (!hasSystemMessage) {
            springMessages.add(new SystemMessage(AIChatConstants.SYSTEM_PROMPT));
        }

        // 转换所有消息
        List<Message> convertedMessages = messages.stream()
                .map(msg -> {
                    String role = msg.getRole() == null ? "user" : msg.getRole();
                    String content = msg.getContent() == null ? "" : msg.getContent();

                    return switch (role) {
                        case "user" -> new UserMessage(content);
                        case "assistant" -> new AssistantMessage(content);
                        case "system" -> new SystemMessage(content);
                        default -> new UserMessage(content);
                    };
                })
                .collect(Collectors.toList());

        springMessages.addAll(convertedMessages);
        return springMessages;
    }

    /**
     * 构造完整的 completion 响应 JSON
     */
    private JsonNode buildCompletionJson(String id, long created, String content,
                                         String finishReason, Map<String, Object> usage) {
        Map<String, Object> message = Map.of(
                "role", "assistant",
                "content", content
        );

        Map<String, Object> choice = Map.of(
                "index", 0,
                "message", message,
                "finish_reason", finishReason
        );

        Map<String, Object> response = new HashMap<>();
        response.put("id", id);
        response.put("object", OBJECT_COMPLETION);
        response.put("created", created);
        response.put("model", MODEL_NAME);
        response.put("choices", List.of(choice));
        response.put("usage", usage);

        return objectMapper.valueToTree(response);
    }

    /**
     * 构造 SSE 数据块
     */
    private String formatSSEChunk(String id, long created, String content) {
        Map<String, Object> delta = Map.of("content", content);
        Map<String, Object> choice = new HashMap<>();
        choice.put("delta", delta);
        choice.put("index", 0);
        choice.put("finish_reason", null);

        Map<String, Object> data = new HashMap<>();
        data.put("id", id);
        data.put("object", OBJECT_COMPLETION_CHUNK);
        data.put("created", created);
        data.put("model", MODEL_NAME);
        data.put("choices", List.of(choice));

        try {
            return "data: " + objectMapper.writeValueAsString(data) + "\n\n";
        } catch (Exception e) {
            log.error("序列化 SSE 响应失败", e);
            return "";
        }
    }

    /**
     * 提取 AI 回复内容（从 JsonNode 中）
     */
    private String extractContentFromResponse(JsonNode response) {
        if (response.has("choices") && response.get("choices").size() > 0) {
            JsonNode messageNode = response.get("choices").get(0).get("message");
            if (messageNode != null && messageNode.has("content")) {
                return messageNode.get("content").asText();
            }
        }
        return null;
    }

    /**
     * 估算 token 数（简化版：中文按字符，英文按空格分词）
     * 实际应用中建议接入 tokenizer 或使用模型返回值
     */
    private int estimateTokens(String text) {
        if (text == null || text.isEmpty()) return 0;
        // 粗略估算：中文字符算 1，英文单词拆分
        String[] words = text.trim().split("\\s+");
        int count = 0;
        for (String word : words) {
            if (!word.isEmpty()) {
                // 每个中文字符视为一个 token，其他作为一个 token
                count += word.replaceAll("[\\u4e00-\\u9fa5]", "C").length();
            }
        }
        return Math.max(count, 1);
    }

    /**
     * 计算 usage 统计
     */
    private Map<String, Object> calculateUsage(List<com.echoes.conversation.domain.chat.entity.dto.MessageDTO> messages, String output) {
        int promptTokens = messages.stream()
                .filter(m -> m.getContent() != null)
                .mapToInt(m -> estimateTokens(m.getContent()))
                .sum();

        int completionTokens = estimateTokens(output);
        int totalTokens = promptTokens + completionTokens;

        return Map.of(
                "prompt_tokens", promptTokens,
                "completion_tokens", completionTokens,
                "total_tokens", totalTokens
        );
    }
}