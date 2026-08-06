package com.echoes.voice.domain.voice.controller;

import com.echoes.health.HealthController;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 语音服务健康检查控制器
 */
@RestController
@RequestMapping("/voice")
public class VoiceHealthController extends HealthController {

    @Override
    protected String getServiceName() {
        return "Echoes-Voice";
    }
}
