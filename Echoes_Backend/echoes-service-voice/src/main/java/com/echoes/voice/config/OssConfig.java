package com.echoes.voice.config;

import com.echoes.voice.config.AliOssProperties;
import com.echoes.voice.common.util.AliOssUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Slf4j
@Configuration
@RequiredArgsConstructor
public class OssConfig {

    private final AliOssProperties aliOssProperties;

    @Bean
    public AliOssUtil aliOssUtil() {
        log.info("Initializing AliOssUtil with endpoint: {}, bucket: {}", 
                aliOssProperties.getEndpoint(), aliOssProperties.getBucketName());
        log.debug("OSS AccessKeyId: {}", aliOssProperties.getAccessKeyId());
        
        return AliOssUtil.builder()
                .endpoint(aliOssProperties.getEndpoint())
                .accessKeyId(aliOssProperties.getAccessKeyId())
                .accessKeySecret(aliOssProperties.getAccessKeySecret())
                .bucketName(aliOssProperties.getBucketName())
                .build();
    }
}
