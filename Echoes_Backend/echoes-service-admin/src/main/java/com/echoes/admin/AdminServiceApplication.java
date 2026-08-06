package com.echoes.admin;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;

/**
 * 管理服务启动类
 */
@SpringBootApplication(scanBasePackages = {"com.echoes.admin"})
@EnableDiscoveryClient
@EnableFeignClients(basePackages = {"com.echoes.admin.domain.governance.client"})
@MapperScan(basePackages = {
        "com.echoes.admin.domain.governance.repository",
        "com.echoes.voice.domain.voice.repository"
})
public class AdminServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(AdminServiceApplication.class, args);
    }
}

