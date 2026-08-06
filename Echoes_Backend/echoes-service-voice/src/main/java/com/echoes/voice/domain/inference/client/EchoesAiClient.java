package com.echoes.voice.domain.inference.client;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DefaultDataBufferFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.socket.client.ReactorNettyWebSocketClient;
import reactor.core.publisher.Flux;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import com.fasterxml.jackson.databind.JsonNode;
import java.net.URI;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Echoes-AI gateway client for TTS sync calls.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class EchoesAiClient {

    private static final String BASE_URL = "lb://echoes-ai";
    private static final String TTS_SYNC_PATH = "/tts/inference/synthesize-text";
    private static final String TTS_STREAM_PATH = "/tts/inference/synthesize-stream";
    private static final String TTS_STREAM_WS_PATH = "/tts/inference/synthesize-stream-ws";
    private static final String WS_EOS_MARKER = "__ECHOES_STREAM_EOS__";
    private static final String VOICE_REF_UPLOAD_PATH = "/internal/voice/ref/upload";
    private static final String VOICE_REF_GET_PATH = "/internal/voice/ref/{refId}";
    private static final String VOICE_ASR_PATH = "/internal/voice/asr";

    private final WebClient.Builder loadBalancedWebClientBuilder;
    private final WebClient directWebClient = WebClient.builder().build();
    private final ReactorNettyWebSocketClient webSocketClient = new ReactorNettyWebSocketClient();
    @Value("${echoes.ai.direct-url:}")
    private String echoesAiDirectUrl;

    private String resolveBaseUrl() {
        if (echoesAiDirectUrl != null && !echoesAiDirectUrl.isBlank()) {
            return echoesAiDirectUrl;
        }
        return BASE_URL;
    }

    private WebClient resolveClient() {
        if (echoesAiDirectUrl != null && !echoesAiDirectUrl.isBlank()) {
            return directWebClient;
        }
        return loadBalancedWebClientBuilder.build();
    }

    public byte[] ttsSync(String text, String refId, String traceId, String sessionId, String turnId) {
        Map<String, Object> body = new HashMap<>();
        body.put("text", text);
        if (refId != null && !refId.isBlank()) {
            body.put("ref_id", refId);
        }
        boolean strictVoice = refId != null && !refId.isBlank() && !"default".equalsIgnoreCase(refId);
        return resolveClient()
                .post()
                .uri(resolveBaseUrl() + TTS_SYNC_PATH)
                .contentType(MediaType.APPLICATION_JSON)
                .header("X-INTERNAL", "1")
                .header("X-STRICT-VOICE", strictVoice ? "1" : "0")
                .header("X-TRACE-ID", traceId != null ? traceId : "")
                .header("X-SESSION-ID", sessionId != null ? sessionId : "")
                .header("X-TURN-ID", turnId != null ? turnId : "")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(byte[].class)
                .block(Duration.ofMinutes(2));
    }

    public Flux<String> synthesizeStream(String text, String voiceName, String traceId, String sessionId, String turnId) {
        // Echoes-AI expects raw text in body and voiceName as query parameter
        String vn = (voiceName == null || voiceName.isBlank()) ? "default" : voiceName;
        boolean strictVoice = !"default".equalsIgnoreCase(vn);
        String encodedVoiceName = java.net.URLEncoder.encode(vn, java.nio.charset.StandardCharsets.UTF_8);
        String pathWithParam = TTS_STREAM_PATH + "?voiceName=" + encodedVoiceName;
        String requestUrl = resolveBaseUrl() + pathWithParam;
        String bodyText = text == null ? "" : text;

        ObjectMapper mapper = new ObjectMapper();
        return resolveClient()
                .post()
                .uri(requestUrl)
                .contentType(MediaType.TEXT_PLAIN)
                .accept(MediaType.APPLICATION_OCTET_STREAM)
                .header("X-INTERNAL", "1")
                .header("X-STRICT-VOICE", strictVoice ? "1" : "0")
                .header("X-TRACE-ID", traceId != null ? traceId : "")
                .header("X-SESSION-ID", sessionId != null ? sessionId : "")
                .header("X-TURN-ID", turnId != null ? turnId : "")
                .bodyValue(bodyText)
                .retrieve()
                .bodyToFlux(byte[].class)
                .doOnSubscribe(s -> log.debug("Echoes-AI stream request start, url={}, voiceName={}, textLen={}",
                        requestUrl, vn, bodyText.length()))
                .doOnNext(bytes -> log.debug("Echoes-AI stream chunk received, bytes={}", bytes == null ? 0 : bytes.length))
                .switchIfEmpty(Flux.defer(() -> {
                    log.warn("Echoes-AI stream returned no audio chunks, url={}, voiceName={}, textLen={}",
                            requestUrl, vn, bodyText.length());
                    return Flux.error(new IllegalStateException("Echoes-AI stream returned no audio chunks"));
                }))
                .doOnComplete(() -> log.debug("Echoes-AI stream request completed, url={}, voiceName={}", requestUrl, vn))
                .map(bytes -> {
                    try {
                        ObjectNode node = mapper.createObjectNode();
                        node.put("type", "audio");
                        node.put("content", (String) null);
                        node.put("isFinal", false);
                        node.put("audioData", java.util.Base64.getEncoder().encodeToString(bytes));
                        return mapper.writeValueAsString(node);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                });
    }

    /**
     * True-stream bridge: keep one downstream HTTP stream to Echoes-AI and forward text deltas as request body stream.
     */
    public Flux<String> synthesizeStream(Flux<String> textStream, String voiceName, String traceId, String sessionId, String turnId) {
        String vn = (voiceName == null || voiceName.isBlank()) ? "default" : voiceName;
        boolean strictVoice = !"default".equalsIgnoreCase(vn);
        String encodedVoiceName = java.net.URLEncoder.encode(vn, StandardCharsets.UTF_8);
        String wsPathWithParam = TTS_STREAM_WS_PATH + "?voiceName=" + encodedVoiceName;
        String wsUrl = resolveWsUrl(resolveBaseUrl(), wsPathWithParam);
        if (wsUrl == null) {
            // No direct ws url (e.g. only lb:// available), fallback to existing HTTP stream path.
            return synthesizeStreamViaHttp(textStream, vn, traceId, sessionId, turnId);
        }

        ObjectMapper mapper = new ObjectMapper();
        Flux<String> normalizedText = textStream
                .map(chunk -> chunk == null ? "" : chunk.trim())
                .map(this::stripSseDataPrefix)
                .filter(chunk -> !chunk.isBlank())
                .doOnSubscribe(s -> log.info("Echoes-AI true-stream upstream text subscribed, voiceName={}", vn))
                .doOnNext(chunk -> log.info("Echoes-AI true-stream upstream text chunk, len={}, preview={}",
                        chunk.length(),
                        chunk.length() > 80 ? chunk.substring(0, 80) + "..." : chunk));

        Flux<byte[]> audioByteFlux = Flux.create(sink -> {
            HttpHeaders headers = new HttpHeaders();
            headers.add("X-INTERNAL", "1");
            headers.add("X-STRICT-VOICE", strictVoice ? "1" : "0");
            headers.add("X-TRACE-ID", traceId != null ? traceId : "");
            headers.add("X-SESSION-ID", sessionId != null ? sessionId : "");
            headers.add("X-TURN-ID", turnId != null ? turnId : "");

            AtomicBoolean receivedAny = new AtomicBoolean(false);
            Flux<String> outboundText = normalizedText.concatWith(Flux.just(WS_EOS_MARKER));

            webSocketClient.execute(
                    URI.create(wsUrl),
                    headers,
                    session -> {
                        Flux<org.springframework.web.reactive.socket.WebSocketMessage> outbound =
                                outboundText.map(session::textMessage);

                        return session.send(outbound)
                                .thenMany(session.receive())
                                .doOnNext(msg -> {
                                    if (msg.getType() == org.springframework.web.reactive.socket.WebSocketMessage.Type.BINARY) {
                                        var db = msg.getPayload();
                                        byte[] bytes = new byte[db.readableByteCount()];
                                        db.read(bytes);
                                        receivedAny.set(true);
                                        sink.next(bytes);
                                        log.info("Echoes-AI true-stream ws chunk received, bytes={}", bytes.length);
                                    }
                                })
                                .doOnError(sink::error)
                                .doOnComplete(() -> {
                                    if (!receivedAny.get()) {
                                        log.warn("Echoes-AI true-stream ws returned no audio chunks, url={}, voiceName={}", wsUrl, vn);
                                        sink.error(new IllegalStateException("Echoes-AI true-stream ws returned no audio chunks"));
                                        return;
                                    }
                                    sink.complete();
                                })
                                .then();
                    }
            )
            .doOnSubscribe(s -> log.info("Echoes-AI true-stream ws request start, url={}, voiceName={}, base={}", wsUrl, vn, resolveBaseUrl()))
            .doOnError(sink::error)
            .subscribe();
        });

        return audioByteFlux
                .doOnComplete(() -> log.info("Echoes-AI true-stream ws request completed, url={}, voiceName={}", wsUrl, vn))
                .map(bytes -> {
                    try {
                        ObjectNode node = mapper.createObjectNode();
                        node.put("type", "audio");
                        node.put("content", (String) null);
                        node.put("isFinal", false);
                        node.put("audioData", java.util.Base64.getEncoder().encodeToString(bytes));
                        return mapper.writeValueAsString(node);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                });
    }

    private Flux<String> synthesizeStreamViaHttp(Flux<String> textStream, String vn, String traceId, String sessionId, String turnId) {
        boolean strictVoice = !"default".equalsIgnoreCase(vn);
        String encodedVoiceName = java.net.URLEncoder.encode(vn, StandardCharsets.UTF_8);
        String pathWithParam = TTS_STREAM_PATH + "?voiceName=" + encodedVoiceName;
        String requestUrl = resolveBaseUrl() + pathWithParam;
        ObjectMapper mapper = new ObjectMapper();

        Flux<String> normalizedText = textStream
                .map(chunk -> chunk == null ? "" : chunk.trim())
                .map(this::stripSseDataPrefix)
                .filter(chunk -> !chunk.isBlank())
                .map(this::toSseEventFrame);

        Flux<DataBuffer> requestBody = normalizedText
                .map(frame -> DefaultDataBufferFactory.sharedInstance.wrap(frame.getBytes(StandardCharsets.UTF_8)));

        return resolveClient()
                .post()
                .uri(requestUrl)
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .accept(MediaType.APPLICATION_OCTET_STREAM)
                .header("X-INTERNAL", "1")
                .header("X-STRICT-VOICE", strictVoice ? "1" : "0")
                .header("X-TRACE-ID", traceId != null ? traceId : "")
                .header("X-SESSION-ID", sessionId != null ? sessionId : "")
                .header("X-TURN-ID", turnId != null ? turnId : "")
                .body(BodyInserters.fromDataBuffers(requestBody))
                .retrieve()
                .bodyToFlux(byte[].class)
                .doOnSubscribe(s -> log.info("Echoes-AI true-stream http request start, url={}, voiceName={}, base={}", requestUrl, vn, resolveBaseUrl()))
                .doOnNext(bytes -> log.info("Echoes-AI true-stream http chunk received, bytes={}", bytes == null ? 0 : bytes.length))
                .switchIfEmpty(Flux.defer(() -> {
                    log.warn("Echoes-AI true-stream http returned no audio chunks, url={}, voiceName={}", requestUrl, vn);
                    return Flux.error(new IllegalStateException("Echoes-AI true-stream http returned no audio chunks"));
                }))
                .doOnComplete(() -> log.info("Echoes-AI true-stream http request completed, url={}, voiceName={}", requestUrl, vn))
                .map(bytes -> {
                    try {
                        ObjectNode node = mapper.createObjectNode();
                        node.put("type", "audio");
                        node.put("content", (String) null);
                        node.put("isFinal", false);
                        node.put("audioData", java.util.Base64.getEncoder().encodeToString(bytes));
                        return mapper.writeValueAsString(node);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                });
    }

    private String resolveWsUrl(String baseUrl, String pathWithParam) {
        if (baseUrl == null || baseUrl.isBlank()) {
            return null;
        }
        if (baseUrl.startsWith("http://")) {
            return "ws://" + baseUrl.substring("http://".length()) + pathWithParam;
        }
        if (baseUrl.startsWith("https://")) {
            return "wss://" + baseUrl.substring("https://".length()) + pathWithParam;
        }
        return null;
    }

    private String stripSseDataPrefix(String raw) {
        if (raw == null) {
            return "";
        }
        String s = raw.trim();
        if (s.startsWith("data:")) {
            return s.substring(5).trim();
        }
        return s;
    }

    private String toSseEventFrame(String chunk) {
        String safe = chunk == null ? "" : chunk;
        return "data: " + safe + "\n\n";
    }

    public JsonNode uploadVoiceReference(byte[] audioData, String filename, String refText, String traceId, String sessionId, String turnId) {
        return uploadVoiceReference(audioData, filename, refText, null, traceId, sessionId, turnId);
    }

    public JsonNode uploadVoiceReference(byte[] audioData, String filename, String refText, String refId, String traceId, String sessionId, String turnId) {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("audio_file", new ByteArrayResource(audioData))
                .filename(filename)
                .contentType(MediaType.APPLICATION_OCTET_STREAM);
        if (refText != null && !refText.isBlank()) {
            builder.part("ref_text", refText);
        }
        if (refId != null && !refId.isBlank()) {
            builder.part("ref_id", refId);
        }

        return resolveClient()
                .post()
                .uri(resolveBaseUrl() + VOICE_REF_UPLOAD_PATH)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .header("X-TRACE-ID", traceId != null ? traceId : "")
                .header("X-SESSION-ID", sessionId != null ? sessionId : "")
                .header("X-TURN-ID", turnId != null ? turnId : "")
                .bodyValue(builder.build())
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block(Duration.ofMinutes(2));
    }

    public JsonNode getVoiceReference(String refId, String traceId, String sessionId, String turnId) {
        return resolveClient()
                .get()
                .uri(resolveBaseUrl() + VOICE_REF_GET_PATH, refId)
                .header("X-TRACE-ID", traceId != null ? traceId : "")
                .header("X-SESSION-ID", sessionId != null ? sessionId : "")
                .header("X-TURN-ID", turnId != null ? turnId : "")
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block(Duration.ofMinutes(1));
    }

    /**
     * 调用 Python ASR 接口进行语音转写（不存储音频）
     *
     * @param audioData 音频数据
     * @param filename 文件名
     * @return 转写文本
     */
    public JsonNode transcribeAudio(byte[] audioData, String filename) {
        MultipartBodyBuilder builder = new MultipartBodyBuilder();
        builder.part("audio_file", new ByteArrayResource(audioData))
                .filename(filename)
                .contentType(MediaType.APPLICATION_OCTET_STREAM);

        return resolveClient()
                .post()
                .uri(resolveBaseUrl() + VOICE_ASR_PATH)
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .bodyValue(builder.build())
                .retrieve()
                .bodyToMono(JsonNode.class)
                .block(Duration.ofMinutes(2));
    }
}
