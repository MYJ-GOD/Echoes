package com.echoes.voice.config;

import com.echoes.voice.common.util.MinioUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Slf4j
@Configuration
@RequiredArgsConstructor
public class MinioConfig {

    private final MinioProperties minioProperties;

    @Bean
    public MinioUtil minioUtil() {
        MinioUtil util = MinioUtil.builder()
                .endpoint(minioProperties.getEndpoint())
                .accessKey(minioProperties.getAccessKey())
                .secretKey(minioProperties.getSecretKey())
                .bucketName(minioProperties.getBucketName())
                .secure(minioProperties.isSecure())
                .build();
        // 启动即确保 bucket 存在；失败仅告警不 crash（上传逻辑本身还有 Python 本地存储 fallback）
        try {
            util.ensureBucket();
        } catch (Exception e) {
            log.error("MinIO bucket ensure failed at startup; storage ops will fail until fixed: {}", e.getMessage());
        }
        return util;
    }
}
