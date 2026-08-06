package com.echoes.voice.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.core.ResolvableType;
import org.springframework.http.HttpInputMessage;
import org.springframework.http.HttpOutputMessage;
import org.springframework.http.MediaType;
import org.springframework.http.converter.GenericHttpMessageConverter;
import org.springframework.http.converter.HttpMessageConverter;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.http.converter.HttpMessageNotWritableException;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import reactor.core.publisher.Flux;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.List;

/**
 * Spring MVC 配置
 * 支持 text/event-stream 作为请求体
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Override
    public void extendMessageConverters(List<HttpMessageConverter<?>> converters) {
        // 添加自定义消息转换器以支持 text/event-stream 作为请求体
        converters.add(0, new TextEventStreamHttpMessageConverter());
    }

    /**
     * 自定义消息转换器，支持将 text/event-stream 请求体解析为 Flux<String>
     * 实现真正的流式处理，逐块处理，不等待全部完成
     */
    private static class TextEventStreamHttpMessageConverter implements GenericHttpMessageConverter<Flux<String>> {

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
        public boolean canRead(Class<?> clazz, MediaType mediaType) {
            return Flux.class.isAssignableFrom(clazz) 
                    && mediaType != null 
                    && mediaType.isCompatibleWith(MediaType.TEXT_EVENT_STREAM);
        }

        @Override
        public boolean canRead(Type type, Class<?> contextClass, MediaType mediaType) {
            if (mediaType == null || !mediaType.isCompatibleWith(MediaType.TEXT_EVENT_STREAM)) {
                return false;
            }
            ResolvableType resolvableType = ResolvableType.forType(type);
            Class<?> resolvedType = resolvableType.resolve();
            if (resolvedType == null || !Flux.class.isAssignableFrom(resolvedType)) {
                return false;
            }
            // 检查是否是 Flux<String>
            ResolvableType genericType = resolvableType.getGeneric(0);
            return genericType != null && String.class.equals(genericType.resolve());
        }

        @Override
        public boolean canWrite(Class<?> clazz, MediaType mediaType) {
            return false; // 只支持读取，不支持写入
        }

        @Override
        public boolean canWrite(Type type, Class<?> contextClass, MediaType mediaType) {
            return false; // 只支持读取，不支持写入
        }

        @Override
        public List<MediaType> getSupportedMediaTypes() {
            return Collections.singletonList(MediaType.TEXT_EVENT_STREAM);
        }

        @Override
        public Flux<String> read(Class<? extends Flux<String>> clazz, HttpInputMessage inputMessage)
                throws IOException, HttpMessageNotReadableException {
            return readInternal(clazz, inputMessage);
        }

        @Override
        public Flux<String> read(Type type, Class<?> contextClass, HttpInputMessage inputMessage)
                throws IOException, HttpMessageNotReadableException {
            return readInternal(null, inputMessage);
        }

        private Flux<String> readInternal(Class<? extends Flux<String>> clazz, HttpInputMessage inputMessage)
                throws IOException, HttpMessageNotReadableException {
            // 读取请求体并转换为 Flux<String>
            // 注意：Spring MVC 是阻塞式的，我们需要将阻塞式 IO 转换为响应式流
            return Flux.create(sink -> {
                try (BufferedReader reader = new BufferedReader(
                        new InputStreamReader(inputMessage.getBody(), StandardCharsets.UTF_8))) {
                    
                    ParseState state = new ParseState();
                    char[] buffer = new char[8192];
                    int bytesRead;
                    
                    while ((bytesRead = reader.read(buffer)) != -1) {
                        String chunk = new String(buffer, 0, bytesRead);
                        state.processChunk(chunk);
                        
                        // 发送完整的事件
                        for (String event : state.events) {
                            if (!event.isEmpty()) {
                                sink.next(event);
                            }
                        }
                    }
                    
                    // 处理最后剩余的数据
                    if (state.buffer.length() > 0) {
                        String remaining = state.buffer.toString().trim();
                        if (!remaining.isEmpty()) {
                            sink.next(remaining);
                        }
                    }
                    
                    sink.complete();
                } catch (IOException e) {
                    sink.error(e);
                }
            });
        }

        @Override
        public void write(Flux<String> flux, MediaType contentType, HttpOutputMessage outputMessage)
                throws IOException, HttpMessageNotWritableException {
            // 不支持写入
            throw new UnsupportedOperationException("Writing Flux<String> is not supported");
        }

        @Override
        public void write(Flux<String> flux, Type type, MediaType contentType, HttpOutputMessage outputMessage)
                throws IOException, HttpMessageNotWritableException {
            // 不支持写入
            throw new UnsupportedOperationException("Writing Flux<String> is not supported");
        }
    }
}

