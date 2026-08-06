package com.echoes.voice.domain.voice.service.impl;

import com.echoes.utils.UuidUtils;
import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import com.echoes.voice.domain.voice.repository.VoiceAssetMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceQualityScoreService {

    private static final BigDecimal MIN_SCORE = BigDecimal.ZERO;
    private static final BigDecimal MAX_SCORE = BigDecimal.ONE;
    private static final BigDecimal DEFAULT_BASE_SCORE = new BigDecimal("0.70");
    private static final BigDecimal SUCCESS_DELTA = new BigDecimal("0.01");
    private static final BigDecimal FAILURE_DELTA = new BigDecimal("0.03");

    private final VoiceAssetMapper voiceAssetMapper;

    public void adjustByInferenceResult(String voiceName, boolean success, String reason) {
        UUID voiceAssetId = parseVoiceAssetId(voiceName);
        if (voiceAssetId == null) {
            return;
        }

        VoiceAsset asset = voiceAssetMapper.selectById(voiceAssetId);
        if (asset == null) {
            return;
        }

        BigDecimal current = asset.getQualityScore() != null ? asset.getQualityScore() : DEFAULT_BASE_SCORE;
        BigDecimal next = success
                ? current.add(SUCCESS_DELTA)
                : current.subtract(FAILURE_DELTA);
        next = clamp01(next).setScale(2, RoundingMode.HALF_UP);

        if (next.compareTo(current) != 0) {
            voiceAssetMapper.updateQualityScore(voiceAssetId, next);
            log.info(
                    "event=voice_quality_score_adjusted voiceAssetId={} voiceName={} success={} reason={} previous={} next={}",
                    voiceAssetId,
                    voiceName,
                    success,
                    reason,
                    current,
                    next
            );
        }
    }

    private UUID parseVoiceAssetId(String voiceName) {
        if (voiceName == null || voiceName.isBlank() || "default".equalsIgnoreCase(voiceName)) {
            return null;
        }
        try {
            return UuidUtils.parseLenient(voiceName);
        } catch (Exception e) {
            return null;
        }
    }

    private BigDecimal clamp01(BigDecimal score) {
        if (score == null) {
            return DEFAULT_BASE_SCORE;
        }
        if (score.compareTo(MIN_SCORE) < 0) {
            return MIN_SCORE;
        }
        if (score.compareTo(MAX_SCORE) > 0) {
            return MAX_SCORE;
        }
        return score;
    }
}
