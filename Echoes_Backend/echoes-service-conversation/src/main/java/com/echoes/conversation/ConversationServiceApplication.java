package com.echoes.conversation;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.data.mongodb.repository.config.EnableMongoRepositories;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 瀵硅瘽鏈嶅姟鍚姩绫?
 */
@SpringBootApplication(scanBasePackages = {"com.echoes.conversation"})
@EnableDiscoveryClient
@EnableFeignClients(basePackages = {"com.echoes.conversation.domain.chat.client"})
@EnableMongoRepositories(basePackages = {"com.echoes.conversation.domain.chat.repository"})
@EnableScheduling
public class ConversationServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(ConversationServiceApplication.class, args);
    }
}

