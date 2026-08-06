package com.echoes.voice.domain.inference.controller;

import com.echoes.voice.domain.inference.client.EchoesAiClient;
import com.echoes.voice.common.util.AliOssUtil;
import com.echoes.voice.domain.voice.entity.po.VoiceRef;
import com.echoes.voice.domain.voice.repository.VoiceRefMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

/**
 * Voice reference proxy endpoints (Echoes-AI gateway).
 * 
 * 閺嬭埖鐎拠瀛樻閿? * - Java 缂佺喍绔撮崗銉ュ經婢跺嫮鎮婄€涙ê鍋嶉敍鍦S閿? * - Python 閸欘亣绀嬬拹?ASR 鐠囧棗鍩嗛崪宀冾唲缂佸啯澧界悰? * - 缁楋箑鎮?Echoes 閺嬭埖鐎憴鍕瘱閿涙ava 閸楁洑绔撮崙鍝勫經閿涘ython 閼宠棄濮忛幍褑顢戠仦? */
@RestController
@RequestMapping("/internal/voice/assets/ref")
@RequiredArgsConstructor
@Slf4j
public class VoiceReferenceController {

    private final EchoesAiClient echoesAiClient;
    private final AliOssUtil aliOssUtil;
    private final VoiceRefMapper voiceRefMapper;
    private final ObjectMapper objectMapper;

    /**
     * 娑撳﹣绱剁拠顓㈢叾閸欏倽鈧啴鐓舵０?     * 
     * 濞翠胶鈻奸敍?     * 1. Java 閻╁瓨甯存稉濠佺炊閸?OSS
     * 2. 鐠嬪啰鏁?Python ASR 鏉╂稖顢戞潪顒€鍟撻敍鍫滅瑝鐎涙ê鍋嶉敍?     * 3. 娣囨繂鐡?VoiceRef 閸掔増鏆熼幑顔肩氨閿涘澃torageKey 娑?OSS 鐠侯垰绶為敍?     * 
     * @return refId, refText, storageKey
     */
    @PostMapping("/upload")
    public ResponseEntity<JsonNode> uploadReference(
            @RequestPart("audio_file") MultipartFile audioFile,
            @RequestParam(value = "ref_text", required = false) String refText,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            byte[] audio = audioFile.getBytes();
            String filename = audioFile.getOriginalFilename() != null
                    ? audioFile.getOriginalFilename()
                    : "voice-ref";

            String refId = UUID.randomUUID().toString();
            String storageKey = "voice_refs/" + refId + getFileExtension(filename);
            String ossUrl = "";
            boolean useOss = true;
            try {
                ossUrl = aliOssUtil.upload(audio, storageKey);
                log.info("Uploaded to OSS: storageKey={}, url={}", storageKey, ossUrl);
            } catch (Exception e) {
                log.error("OSS upload failed, falling back to Python storage", e);
                useOss = false;
            }

            if (!useOss) {
                JsonNode result = echoesAiClient.uploadVoiceReference(audio, filename, refText, refId, traceId, sessionId, turnId);
                boolean embeddingGenerated = result != null && result.path("embedding_generated").asBoolean(false);
                if (!embeddingGenerated) {
                    String embeddingError = result != null ? result.path("embedding_error").asText("unknown") : "null response";
                    throw new IllegalStateException("Python embedding generation failed: " + embeddingError);
                }

                String pythonRefId = result.has("ref_id") ? result.get("ref_id").asText() : refId;
                String audioPath = result.has("audio_path") ? result.get("audio_path").asText() : "";

                VoiceRef voiceRef = VoiceRef.builder()
                        .refId(pythonRefId)
                        .ownerUserId(userId != null ? UUID.fromString(userId) : null)
                        .conversationId(null)
                        .storageKey(audioPath)
                        .format(getFileExtension(filename).replace(".", ""))
                        .durationMs(estimateAudioDurationMs(audio))
                        .expiresAt(LocalDateTime.now().plusDays(7))
                        .createTime(LocalDateTime.now())
                        .build();

                try {
                    voiceRefMapper.insert(voiceRef);
                    log.info("Saved VoiceRef to database (Python fallback): refId={}, storageKey={}", pythonRefId, audioPath);
                } catch (Exception ex) {
                    log.error("Failed to save VoiceRef to database (Python fallback): {}", ex.getMessage());
                }

                return ResponseEntity.ok(result);
            }

            String finalRefText = refText;
            if (refText == null || refText.isBlank()) {
                try {
                    JsonNode asrResult = echoesAiClient.transcribeAudio(audio, filename);
                    finalRefText = asrResult.has("text") ? asrResult.get("text").asText() : "";
                    log.info("ASR transcription: {}", finalRefText);
                } catch (Exception e) {
                    log.warn("ASR transcription failed: {}", e.getMessage());
                    finalRefText = "";
                }
            }

            VoiceRef voiceRef = VoiceRef.builder()
                    .refId(refId)
                    .ownerUserId(userId != null ? UUID.fromString(userId) : null)
                    .conversationId(null)
                    .storageKey(storageKey)
                    .format(getFileExtension(filename).replace(".", ""))
                    .durationMs(estimateAudioDurationMs(audio))
                    .expiresAt(LocalDateTime.now().plusDays(7))
                    .createTime(LocalDateTime.now())
                    .build();

            try {
                voiceRefMapper.insert(voiceRef);
                log.info("Saved VoiceRef to database: refId={}, storageKey={}", refId, storageKey);
            } catch (Exception e) {
                log.error("Failed to save VoiceRef to database: {}", e.getMessage());
            }

            // ASR result is returned immediately; embedding extraction runs in background.
            triggerEmbeddingExtractionAsync(audio, filename, finalRefText, refId, traceId, sessionId, turnId);

            ObjectNode response = objectMapper.createObjectNode();
            response.put("ref_id", refId);
            response.put("ref_text", finalRefText != null ? finalRefText : "");
            response.put("storage_key", storageKey);
            response.put("url", ossUrl);

            return ResponseEntity.ok(response);

        } catch (Exception e) {
            log.error("Voice reference upload failed", e);
            return ResponseEntity.internalServerError().build();
        }
    }

    @GetMapping("/{refId}")
    public ResponseEntity<JsonNode> getReference(
            @PathVariable("refId") String refId,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId) {
        try {
            // First check local DB record
            VoiceRef voiceRef = voiceRefMapper.selectById(refId);
            if (voiceRef != null) {
                String signedUrl = "";
                String storageKey = voiceRef.getStorageKey();
                
                // 濡偓閺?storageKey 閺?OSS 鐠侯垰绶炴潻妯绘Ц閺堫剙婀寸捄顖氱窞
                if (storageKey != null && storageKey.startsWith("voice_refs/")) {
                    // OSS object key, generate signed URL
                    try {
                        signedUrl = aliOssUtil.generatePresignedUrl(storageKey, 10);
                    } catch (Exception e) {
                        log.warn("Failed to generate signed URL: {}", e.getMessage());
                    }
                } else if (storageKey != null && !storageKey.isEmpty()) {
                    // Local path or already-signed URL
                    signedUrl = storageKey;
                }

                ObjectNode response = objectMapper.createObjectNode();
                response.put("ref_id", voiceRef.getRefId());
                response.put("storage_key", storageKey);
                response.put("url", signedUrl);
                response.put("exists", true);
                return ResponseEntity.ok(response);
            }
            
            // Fallback: 娴?Python 閼惧嘲褰?
            JsonNode result = echoesAiClient.getVoiceReference(refId, traceId, sessionId, turnId);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            log.error("Voice reference get failed: {}", refId, e);
            return ResponseEntity.internalServerError().build();
        }
    }

    /**
     * Generate a presigned URL for an existing storage key.
     * Query param: storage_key
     */
    @GetMapping("/signed")
    public ResponseEntity<JsonNode> getSignedUrl(
            @RequestParam("storage_key") String storageKey,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId) {
        try {
            String signed = aliOssUtil.generatePresignedUrl(storageKey, 10); // 10 minutes
            ObjectNode node = objectMapper.createObjectNode();
            node.put("url", signed);
            node.put("storage_key", storageKey);
            return ResponseEntity.ok(node);
        } catch (Exception e) {
            log.error("Generate signed url failed for storage_key {}: {}", storageKey, e.getMessage());
            return ResponseEntity.internalServerError().build();
        }
    }

    @PostMapping("/upload-object")
    public ResponseEntity<JsonNode> uploadObject(
            @RequestPart("audio_file") MultipartFile audioFile,
            @RequestParam("object_name") String objectName,
            @RequestParam(value = "ref_id", required = false) String refId,
            @RequestHeader(value = "X-TRACE-ID", required = false) String traceId,
            @RequestHeader(value = "X-SESSION-ID", required = false) String sessionId,
            @RequestHeader(value = "X-TURN-ID", required = false) String turnId) {
        try {
            byte[] audio = audioFile.getBytes();
            // Use AliOssUtil bean to upload with provided objectName
            AliOssUtil ossUtil = this.aliOssUtil;
            // If AliOssUtil not available, fallback to echoesAiClient upload method using filename
            String publicUrl = null;
            try {
                publicUrl = aliOssUtil.upload(audio, objectName);
            } catch (Exception e) {
                log.warn("Direct OSS upload failed, falling back to EchoesAiClient uploadVoiceReference", e);
                JsonNode result = echoesAiClient.uploadVoiceReference(audio, audioFile.getOriginalFilename() != null ? audioFile.getOriginalFilename() : "audio.wav", null, traceId, sessionId, turnId);
                return ResponseEntity.ok(result);
            }

            ObjectNode node = objectMapper.createObjectNode();
            node.put("storage_key", objectName);
            node.put("url", publicUrl);
            if (refId != null) node.put("ref_id", refId);
            return ResponseEntity.ok(node);
        } catch (Exception e) {
            log.error("Upload object failed", e);
            return ResponseEntity.internalServerError().build();
        }
    }
    
    private String getFileExtension(String filename) {
        if (filename == null) return ".wav";
        int lastDot = filename.lastIndexOf('.');
        return lastDot > 0 ? filename.substring(lastDot) : ".wav";
    }

    private Integer estimateAudioDurationMs(byte[] audioBytes) {
        if (audioBytes == null || audioBytes.length < 44) {
            return null;
        }
        try {
            if (!(audioBytes[0] == 'R' && audioBytes[1] == 'I' && audioBytes[2] == 'F' && audioBytes[3] == 'F'
                    && audioBytes[8] == 'W' && audioBytes[9] == 'A' && audioBytes[10] == 'V' && audioBytes[11] == 'E')) {
                return null;
            }

            int channels = Short.toUnsignedInt(ByteBuffer.wrap(audioBytes, 22, 2).order(ByteOrder.LITTLE_ENDIAN).getShort());
            int sampleRate = ByteBuffer.wrap(audioBytes, 24, 4).order(ByteOrder.LITTLE_ENDIAN).getInt();
            int bitsPerSample = Short.toUnsignedInt(ByteBuffer.wrap(audioBytes, 34, 2).order(ByteOrder.LITTLE_ENDIAN).getShort());
            if (channels <= 0 || sampleRate <= 0 || bitsPerSample <= 0) {
                return null;
            }

            int dataSize = -1;
            for (int i = 12; i + 8 <= audioBytes.length; ) {
                if (audioBytes[i] == 'd' && audioBytes[i + 1] == 'a' && audioBytes[i + 2] == 't' && audioBytes[i + 3] == 'a') {
                    dataSize = ByteBuffer.wrap(audioBytes, i + 4, 4).order(ByteOrder.LITTLE_ENDIAN).getInt();
                    break;
                }
                int chunkSize = ByteBuffer.wrap(audioBytes, i + 4, 4).order(ByteOrder.LITTLE_ENDIAN).getInt();
                if (chunkSize < 0) {
                    return null;
                }
                i += 8 + chunkSize + (chunkSize % 2);
            }
            if (dataSize <= 0) {
                return null;
            }

            double bytesPerSecond = sampleRate * channels * (bitsPerSample / 8.0);
            if (bytesPerSecond <= 0) {
                return null;
            }
            return (int) Math.round((dataSize * 1000.0) / bytesPerSecond);
        } catch (Exception e) {
            log.debug("Failed to estimate reference audio duration: {}", e.getMessage());
            return null;
        }
    }

    private void triggerEmbeddingExtractionAsync(
            byte[] audio,
            String filename,
            String refText,
            String refId,
            String traceId,
            String sessionId,
            String turnId
    ) {
        CompletableFuture.runAsync(() -> {
            long startMs = System.currentTimeMillis();
            try {
                log.info("Async embedding extraction started: refId={}", refId);
                JsonNode pyResult = echoesAiClient.uploadVoiceReference(audio, filename, refText, refId, traceId, sessionId, turnId);
                boolean embeddingGenerated = pyResult != null && pyResult.path("embedding_generated").asBoolean(false);
                if (!embeddingGenerated) {
                    String embeddingError = pyResult != null ? pyResult.path("embedding_error").asText("unknown") : "null response";
                    log.warn("Async embedding extraction failed: refId={}, err={}", refId, embeddingError);
                    return;
                }
                log.info(
                        "Async embedding extraction completed: refId={}, costMs={}",
                        refId,
                        (System.currentTimeMillis() - startMs)
                );
            } catch (Exception ex) {
                log.warn("Async embedding extraction exception: refId={}, err={}", refId, ex.getMessage(), ex);
            }
        });
    }
}

