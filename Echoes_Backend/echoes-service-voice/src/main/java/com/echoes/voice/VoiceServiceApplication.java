package com.echoes.voice;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 语音服务启动类
 */
@SpringBootApplication(scanBasePackages = {"com.echoes.voice"})
@ConfigurationPropertiesScan
@EnableDiscoveryClient
@EnableFeignClients(basePackages = {"com.echoes.voice"})
@MapperScan("com.echoes.voice.domain.voice.repository")
public class VoiceServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(VoiceServiceApplication.class, args);
    }
}

