package com.echoes.user.domain.user.controller;

import com.echoes.health.HealthController;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 用户服务健康检查控制器
 */
@RestController
@RequestMapping("/user")
public class UserHealthController extends HealthController {

    @Override
    protected String getServiceName() {
        return "Echoes-User";
    }
}
