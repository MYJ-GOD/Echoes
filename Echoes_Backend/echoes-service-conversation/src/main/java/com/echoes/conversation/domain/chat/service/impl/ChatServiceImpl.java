package com.echoes.conversation.domain.chat.service.impl;

import com.echoes.conversation.domain.chat.client.DashScopeAiClient;
import com.echoes.conversation.domain.chat.entity.dto.MessageDTO;
import com.echoes.conversation.domain.chat.service.IChatService;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.List;

/**
 * AI对话服务实现
 * 封装DashScope AI客户端调用
 *
 * @author echoes
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ChatServiceImpl implements IChatService {

    private final DashScopeAiClient dashScopeAiClient;

    /**
     * 执行简单对话
     * 仅发送单条消息并获取AI响应，不维护会话上下文
     *
     * @param message 用户输入的消息内容
     * @return AI生成的响应文本
     */
    @Override
    public String simpleChat(String message) {
        log.debug("执行简单对话，消息: {}", message);
        return dashScopeAiClient.simpleChat(message);
    }

    /**
     * 执行完整对话
     * 发送消息列表（包含对话历史）给AI，支持自定义生成参数
     *
     * @param messages  消息历史列表，包含角色和内容
     * @param temperature 生成温度，控制随机性（0-2），值越高越随机
     * @param topP      Top-P采样参数，控制生成多样性（0-1）
     * @param maxTokens 最大生成token数量
     * @return AI响应的JSON节点，包含生成内容和其他元数据
     */
    @Override
    public JsonNode chat(List<MessageDTO> messages, Double temperature, Double topP, Integer maxTokens) {
        log.debug("执行完整对话，消息数: {}, temperature: {}, topP: {}, maxTokens: {}",
                messages == null ? 0 : messages.size(), temperature, topP, maxTokens);
        return dashScopeAiClient.chat(messages, temperature, topP, maxTokens);
    }

    /**
     * 执行流式对话
     * 以流式方式接收AI响应，适用于需要实时显示生成内容的场景
     *
     * @param messages  消息历史列表
     * @param temperature 生成温度
     * @param topP      Top-P采样参数
     * @param maxTokens 最大生成token数量
     * @return 包含AI生成内容的响应流
     */
    @Override
    public Flux<String> chatStream(List<MessageDTO> messages, Double temperature, Double topP, Integer maxTokens) {
        log.debug("执行流式对话，消息数: {}, temperature: {}, topP: {}, maxTokens: {}",
                messages == null ? 0 : messages.size(), temperature, topP, maxTokens);
        return dashScopeAiClient.chatStream(messages, temperature, topP, maxTokens);
    }

    /**
     * 获取可用的AI模型列表
     *
     * @return 模型列表的JSON表示
     */
    @Override
    public JsonNode listModels() {
        log.debug("获取模型列表");
        return dashScopeAiClient.listModels();
    }
}
