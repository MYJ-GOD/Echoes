package com.echoes.voice.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "sky.jwt")
public class JwtProperties {

    private String userSecretKey;
    private long userTtl = 7200000L;
    private String userTokenName = "token";

    private String adminSecretKey;
    private long adminTtl = 7200000L;
}
