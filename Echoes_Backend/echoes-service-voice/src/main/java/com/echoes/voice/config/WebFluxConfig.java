package com.echoes.voice.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.core.ResolvableType;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.http.MediaType;
import org.springframework.http.ReactiveHttpInputMessage;
import org.springframework.http.codec.HttpMessageReader;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.web.reactive.config.WebFluxConfigurer;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * WebFlux 配置
 * 支持 text/event-stream 作为请求体
 */
@Configuration
public class WebFluxConfig implements WebFluxConfigurer {

    @Override
    public void configureHttpMessageCodecs(ServerCodecConfigurer configurer) {
        // 添加自定义消息转换器以支持 text/event-stream 作为请求体
        configurer.customCodecs().register(new TextEventStreamMessageReader());
    }

    /**
     * 自定义消息转换器，支持将 text/event-stream 请求体解析为 Flux<String>
     * 实现真正的流式处理，逐 DataBuffer 处理，不等待全部完成
     */
    private static class TextEventStreamMessageReader implements HttpMessageReader<String> {

        /**
         * SSE 解析状态
         */
        private static class ParseState {
            final StringBuilder buffer = new StringBuilder();
            final List<String> events = new java.util.ArrayList<>();
            
            ParseState processChunk(String chunk) {
                buffer.append(chunk);
                String content = buffer.toString();
                events.clear();
                
                // 提取完整的 SSE 事件
                String[] lines = content.split("\n", -1);
                StringBuilder currentEvent = new StringBuilder();
                StringBuilder remaining = new StringBuilder();
                
                for (int i = 0; i < lines.length; i++) {
                    String line = lines[i];
                    
                    if (line.startsWith("data: ")) {
                        // 如果之前有未完成的事件，先保存
                        if (currentEvent.length() > 0) {
                            String eventData = currentEvent.toString().trim();
                            if (!eventData.isEmpty()) {
                                events.add(eventData);
                            }
                            currentEvent = new StringBuilder();
                        }
                        
                        // 提取 data: 后的内容
                        String data = line.substring(6).trim();
                        currentEvent.append(data);
                        
                        // 检查下一行是否为空（SSE 事件结束标记）
                        if (i + 1 < lines.length && lines[i + 1].trim().isEmpty()) {
                            // 完整事件
                            String eventData = currentEvent.toString().trim();
                            if (!eventData.isEmpty()) {
                                events.add(eventData);
                            }
                            currentEvent = new StringBuilder();
                            i++; // 跳过空行
                        }
                    } else if (line.trim().isEmpty()) {
                        // 空行表示事件结束
                        if (currentEvent.length() > 0) {
                            String eventData = currentEvent.toString().trim();
                            if (!eventData.isEmpty()) {
                                events.add(eventData);
                            }
                            currentEvent = new StringBuilder();
                        }
                    } else if (currentEvent.length() > 0) {
                        // 继续当前事件（多行数据）
                        currentEvent.append("\n").append(line);
                    } else {
                        // 不属于任何事件的行，保留到剩余缓冲区
                        if (remaining.length() > 0) {
                            remaining.append("\n");
                        }
                        remaining.append(line);
                    }
                }
                
                // 保存未完成的事件到剩余缓冲区
                if (currentEvent.length() > 0) {
                    if (remaining.length() > 0) {
                        remaining.append("\n");
                    }
                    remaining.append("data: ").append(currentEvent.toString());
                }
                
                // 更新缓冲区（只保留未处理的部分）
                buffer.setLength(0);
                buffer.append(remaining);
                
                return this;
            }
        }

        @Override
        public boolean canRead(ResolvableType elementType, MediaType mediaType) {
            return (mediaType != null && mediaType.isCompatibleWith(MediaType.TEXT_EVENT_STREAM))
                    && elementType.getRawClass() == String.class;
        }

        @Override
        public List<MediaType> getReadableMediaTypes() {
            return Collections.singletonList(MediaType.TEXT_EVENT_STREAM);
        }

        @Override
        public Flux<String> read(ResolvableType elementType, ReactiveHttpInputMessage message, Map<String, Object> hints) {
            // 真正的流式处理：逐 DataBuffer 处理，不等待全部完成
            // 使用 ParseState 维护缓冲区，处理跨 DataBuffer 的完整 SSE 事件
            return message.getBody()
                    .map(dataBuffer -> {
                        try {
                            // 读取 DataBuffer 内容
                            byte[] bytes = new byte[dataBuffer.readableByteCount()];
                            dataBuffer.read(bytes);
                            return new String(bytes, StandardCharsets.UTF_8);
                        } finally {
                            DataBufferUtils.release(dataBuffer);
                        }
                    })
                    .scan(new ParseState(), (state, chunk) -> {
                        // 处理新的 chunk，更新状态
                        state.processChunk(chunk);
                        return state;
                    })
                    .skip(1) // 跳过初始状态
                    .flatMap(state -> {
                        // 返回完整的事件
                        return Flux.fromIterable(state.events);
                    })
                    .filter(event -> !event.isEmpty());
        }

        @Override
        public Mono<String> readMono(ResolvableType elementType, ReactiveHttpInputMessage message, Map<String, Object> hints) {
            return read(elementType, message, hints).next();
        }
    }
}

