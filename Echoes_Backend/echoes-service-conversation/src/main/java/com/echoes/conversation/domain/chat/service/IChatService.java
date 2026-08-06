package com.echoes.conversation.domain.chat.service;

import com.echoes.conversation.domain.chat.entity.dto.MessageDTO;
import com.fasterxml.jackson.databind.JsonNode;
import reactor.core.publisher.Flux;

import java.util.List;

/**
 * AI对话服务接口
 * 封装DashScope AI客户端调用，提供标准化的对话接口
 */
public interface IChatService {

    /**
     * 简单对话 - 单轮问答
     * 
     * @param message 用户消息
     * @return AI 回复
     */
    String simpleChat(String message);

    /**
     * 完整对话接口 - 支持多轮对话
     * 
     * @param messages 消息列表
     * @param temperature 温度参数
     * @param topP top_p参数
     * @param maxTokens 最大token数
     * @return 对话响应
     */
    JsonNode chat(List<MessageDTO> messages, Double temperature, Double topP, Integer maxTokens);

    /**
     * 流式对话接口
     * 
     * @param messages 消息列表
     * @param temperature 温度参数
     * @param topP top_p参数
     * @param maxTokens 最大token数
     * @return 流式响应
     */
    Flux<String> chatStream(List<MessageDTO> messages, Double temperature, Double topP, Integer maxTokens);

    /**
     * 获取可用模型列表
     * 
     * @return 模型列表
     */
    JsonNode listModels();
}
