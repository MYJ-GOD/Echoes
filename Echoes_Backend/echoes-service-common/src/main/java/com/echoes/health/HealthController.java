package com.echoes.health;

import org.springframework.web.bind.annotation.GetMapping;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 健康检查控制器基类
 * 用于检查服务是否正常运行
 *
 * @author echoes
 */
public class HealthController {

    /**
     * 健康检查接口
     * @return 服务健康状态
     */
    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> result = new HashMap<>();
        result.put("status", "UP");
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", getServiceName() + " 服务运行正常");
        result.put("jdk", System.getProperty("java.version"));
        result.put("springBoot", org.springframework.boot.SpringBootVersion.getVersion());
        return result;
    }

    /**
     * 就绪检查接口
     * 检查服务依赖是否都已就绪
     * @return 服务就绪状态
     */
    @GetMapping("/ready")
    public Map<String, Object> ready() {
        Map<String, Object> result = new HashMap<>();
        result.put("ready", true);
        result.put("timestamp", LocalDateTime.now().toString());
        result.put("message", getServiceName() + " 服务已就绪");
        return result;
    }

    /**
     * 获取服务名称
     * @return 服务名称
     */
    protected String getServiceName() {
        return "Echoes";
    }
}
