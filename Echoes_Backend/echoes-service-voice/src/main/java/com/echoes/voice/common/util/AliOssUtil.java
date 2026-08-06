package com.echoes.voice.common.util;

import com.aliyun.oss.ClientException;
import com.aliyun.oss.HttpMethod;
import com.aliyun.oss.OSS;
import com.aliyun.oss.OSSClientBuilder;
import com.aliyun.oss.OSSException;
import com.aliyun.oss.model.GeneratePresignedUrlRequest;
import com.echoes.exception.BusinessException;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.net.URL;
import java.util.Date;

@Data
@AllArgsConstructor
@Slf4j
@Builder
public class AliOssUtil {

    private String endpoint;
    private String accessKeyId;
    private String accessKeySecret;
    private String bucketName;

    private volatile OSS ossClient;

    private OSS getOssClient() {
        if (ossClient == null) {
            synchronized (this) {
                if (ossClient == null) {
                    ossClient = new OSSClientBuilder().build(endpoint, accessKeyId, accessKeySecret);
                }
            }
        }
        return ossClient;
    }

    public void shutdown() {
        if (ossClient != null) {
            synchronized (this) {
                if (ossClient != null) {
                    try {
                        ossClient.shutdown();
                    } catch (Exception e) {
                        log.warn("Failed to shutdown OSS client", e);
                    } finally {
                        ossClient = null;
                    }
                }
            }
        }
    }

    public String upload(byte[] bytes, String objectName) {
        OSS client = getOssClient();
        try {
            client.putObject(bucketName, objectName, new ByteArrayInputStream(bytes));
        } catch (OSSException | ClientException ex) {
            throw new BusinessException("OSS upload failed: " + ex.getMessage());
        }

        return "https://" + bucketName + "." + endpoint + "/" + objectName;
    }

    public String generatePresignedUrl(String objectName, int expirationMinutes) {
        OSS client = getOssClient();
        try {
            Date expiration = new Date(System.currentTimeMillis() + expirationMinutes * 60L * 1000L);
            GeneratePresignedUrlRequest request = new GeneratePresignedUrlRequest(bucketName, objectName, HttpMethod.GET);
            request.setExpiration(expiration);
            URL url = client.generatePresignedUrl(request);
            return url.toString();
        } catch (OSSException | ClientException ex) {
            throw new BusinessException("OSS presigned url failed: " + ex.getMessage());
        }
    }

    public String extractObjectNameFromUrl(String url) {
        if (url == null || url.isBlank()) {
            return null;
        }
        try {
            URI uri = URI.create(url);
            String path = uri.getPath();
            if (path == null || path.isBlank()) {
                return null;
            }
            return path.startsWith("/") ? path.substring(1) : path;
        } catch (Exception e) {
            log.debug("Failed to parse OSS url: {}", e.getMessage());
            return null;
        }
    }
}
