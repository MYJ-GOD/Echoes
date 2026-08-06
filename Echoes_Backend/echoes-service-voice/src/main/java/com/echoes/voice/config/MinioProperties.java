package com.echoes.voice.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * MinIO 对象存储配置属性
 */
@Data
@Component
@ConfigurationProperties(prefix = "echoes.minio")
public class MinioProperties {

    /** MinIO 服务地址，含协议，如 http://localhost:9000 */
    private String endpoint;

    /** 访问密钥（MINIO_ROOT_USER） */
    private String accessKey;

    /** 访问密钥（MINIO_ROOT_PASSWORD） */
    private String secretKey;

    /** 存储桶名称 */
    private String bucketName;

    /** 是否使用 HTTPS */
    private boolean secure = false;
}
