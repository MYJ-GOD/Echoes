package com.echoes.conversation.domain.chat.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/**
 * 句子分割器服务
 * 将 LLM token 流式输入转换为句子级别输出
 * 基于标点符号或长度阈值进行分割
 */
@Slf4j
@Service
public class SentenceSplitter {

    // 分句正则：按句号、问号、感叹号、换行符分隔
    private static final Pattern SENTENCE_PATTERN = Pattern.compile("([\\u3002\\uff1f\\uff01\\n]+)");

    // 句子最大长度阈值（字符数）
    private static final int MAX_SENTENCE_LENGTH = 240;

    /**
     * 将 token 流转换为句子流
     * 累积 tokens 直到形成完整句子，然后输出句子
     *
     * @param tokenFlux LLM token 流
     * @return 句子流，每个元素是一个完整句子
     */
    public Flux<String> splitIntoSentences(Flux<String> tokenFlux) {
        return Flux.create(sink -> {
            StringBuilder buffer = new StringBuilder();

            tokenFlux.subscribe(
                token -> {
                    if (token == null || token.trim().isEmpty()) {
                        return;
                    }

                    synchronized (buffer) {
                        buffer.append(token);
                    }

                    // 检查是否有完整的句子
                    List<String> completedSentences;
                    synchronized (buffer) {
                        completedSentences = extractCompletedSentences(buffer);
                    }

                    // 输出所有完成的句子
                    for (String sentence : completedSentences) {
                        log.info("生成完整句子: {}", sentence);
                        sink.next(sentence);
                    }

                    // 检查缓冲区长度是否超过阈值
                    synchronized (buffer) {
                        if (buffer.length() >= MAX_SENTENCE_LENGTH) {
                            String remainingText = buffer.toString().trim();
                            if (!remainingText.isEmpty()) {
                                log.info("句子长度超过阈值，强制输出: {}", remainingText);
                                sink.next(remainingText);
                                buffer.setLength(0); // 清空缓冲区
                            }
                        }
                    }
                },
                error -> {
                    log.error("处理 token 流时出错", error);
                    sink.error(error);
                },
                () -> {
                    // 处理流结束时剩余的文本
                    String remaining;
                    synchronized (buffer) {
                        remaining = buffer.toString().trim();
                    }
                    if (!remaining.isEmpty()) {
                        log.info("流结束，输出剩余句子: {}", remaining);
                        sink.next(remaining);
                    }
                    sink.complete();
                }
            );
        });
    }

    /**
     * 从缓冲区中提取完整的句子
     * 基于标点符号识别句子边界
     *
     * @param buffer 文本缓冲区
     * @return 提取的完整句子列表
     */
    private List<String> extractCompletedSentences(StringBuilder buffer) {
        List<String> sentences = new ArrayList<>();
        String text = buffer.toString();

        // 使用正则匹配找到句子结束位置
        java.util.regex.Matcher matcher = SENTENCE_PATTERN.matcher(text);
        int lastEnd = 0;

        while (matcher.find()) {
            int end = matcher.end();
            String sentence = text.substring(lastEnd, end).trim();
            if (!sentence.isEmpty()) {
                sentences.add(sentence);
            }
            lastEnd = end;
        }

        // 移除已提取的句子内容
        if (lastEnd > 0) {
            buffer.delete(0, lastEnd);
        }

        return sentences;
    }
}
