package com.echoes.voice.common.util;

import com.echoes.exception.BusinessException;
import io.minio.BucketExistsArgs;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.http.Method;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.util.Locale;
import java.util.Map;

@Data
@AllArgsConstructor
@Slf4j
@Builder
public class MinioUtil {

    /** 上传后返回的预签名 URL 有效期（分钟） */
    public static final int UPLOAD_URL_EXPIRATION_MINUTES = 60;

    private String endpoint;
    private String accessKey;
    private String secretKey;
    private String bucketName;
    private boolean secure;

    private volatile MinioClient minioClient;
    private volatile boolean bucketEnsured = false;

    private static final Map<String, String> CONTENT_TYPES = Map.of(
            ".wav", "audio/wav",
            ".mp3", "audio/mpeg",
            ".ogg", "audio/ogg",
            ".flac", "audio/flac",
            ".pcm", "audio/basic",
            ".pt", "application/octet-stream",
            ".bin", "application/octet-stream"
    );

    private MinioClient getMinioClient() {
        if (minioClient == null) {
            synchronized (this) {
                if (minioClient == null) {
                    String endpointUrl = endpoint;
                    if (!endpointUrl.startsWith("http://") && !endpointUrl.startsWith("https://")) {
                        endpointUrl = (secure ? "https://" : "http://") + endpointUrl;
                    }
                    minioClient = MinioClient.builder()
                            .endpoint(endpointUrl)
                            .credentials(accessKey, secretKey)
                            .build();
                    log.info("MinIO client initialized: endpoint={}, bucket={}, secure={}",
                            endpointUrl, bucketName, secure);
                }
            }
        }
        return minioClient;
    }

    /**
     * 启动时确保 bucket 存在（幂等）。
     * 失败抛 BusinessException，由调用方决定告警还是继续。
     */
    public void ensureBucket() {
        try {
            MinioClient client = getMinioClient();
            boolean exists = client.bucketExists(BucketExistsArgs.builder().bucket(bucketName).build());
            if (!exists) {
                client.makeBucket(MakeBucketArgs.builder().bucket(bucketName).build());
                log.info("MinIO bucket created: {}", bucketName);
            }
            bucketEnsured = true;
        } catch (Exception e) {
            bucketEnsured = false;
            throw new BusinessException("MinIO ensureBucket failed: " + e.getMessage());
        }
    }

    public void shutdown() {
        // MinioClient 无显式 shutdown；置空引用便于重建
        minioClient = null;
        bucketEnsured = false;
    }

    /**
     * 上传对象，返回预签名 GET URL（bucket 私有，读取必须签名）。
     */
    public String upload(byte[] bytes, String objectName) {
        MinioClient client = getMinioClient();
        try {
            client.putObject(PutObjectArgs.builder()
                    .bucket(bucketName)
                    .object(objectName)
                    .stream(new ByteArrayInputStream(bytes), bytes.length, -1)
                    .contentType(resolveContentType(objectName))
                    .build());
        } catch (Exception ex) {
            throw new BusinessException("MinIO upload failed: " + ex.getMessage());
        }
        return generatePresignedUrl(objectName, UPLOAD_URL_EXPIRATION_MINUTES);
    }

    /**
     * 生成预签名 GET URL。expirationMinutes 转换为秒，MinIO 上限 7 天。
     */
    public String generatePresignedUrl(String objectName, int expirationMinutes) {
        MinioClient client = getMinioClient();
        try {
            return client.getPresignedObjectUrl(
                    GetPresignedObjectUrlArgs.builder()
                            .method(Method.GET)
                            .bucket(bucketName)
                            .object(objectName)
                            .expiry(expirationMinutes * 60)
                            .build());
        } catch (Exception ex) {
            throw new BusinessException("MinIO presigned url failed: " + ex.getMessage());
        }
    }

    /**
     * 从 URL 提取 objectName，兼容三种输入：
     * 1) MinIO URL  http://host:port/{bucket}/{key}   → {key}（剥离 bucket 前缀）
     * 2) OSS URL    https://{bucket}.endpoint/{key}  → {key}
     * 3) 裸 key     voice_models/xxx.pt              → 原样返回
     */
    public String extractObjectNameFromUrl(String url) {
        if (url == null || url.isBlank()) {
            return null;
        }
        String trimmed = url.trim();
        String path = trimmed;
        try {
            if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                URI uri = URI.create(trimmed);
                path = uri.getPath();
                if (path == null || path.isBlank()) {
                    return null;
                }
            }
            path = path.startsWith("/") ? path.substring(1) : path;
            if (bucketName != null && !bucketName.isBlank()
                    && (path.equals(bucketName) || path.startsWith(bucketName + "/"))) {
                path = path.substring(bucketName.length());
                path = path.startsWith("/") ? path.substring(1) : path;
            }
            return path;
        } catch (Exception e) {
            log.debug("Failed to parse MinIO url: {}", e.getMessage());
            return null;
        }
    }

    private String resolveContentType(String objectName) {
        int i = objectName.lastIndexOf('.');
        if (i < 0) {
            return "application/octet-stream";
        }
        return CONTENT_TYPES.getOrDefault(objectName.substring(i).toLowerCase(Locale.ROOT),
                "application/octet-stream");
    }
}
