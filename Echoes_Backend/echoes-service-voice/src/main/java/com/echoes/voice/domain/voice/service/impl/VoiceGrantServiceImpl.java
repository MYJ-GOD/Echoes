package com.echoes.voice.domain.voice.service.impl;

import com.echoes.voice.client.UserServiceFeignClient;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.voice.entity.dto.CreateGrantRequestDTO;
import com.echoes.voice.domain.voice.entity.po.VoiceAsset;
import com.echoes.voice.domain.voice.entity.po.VoiceAuditLog;
import com.echoes.voice.domain.voice.entity.po.VoiceGrant;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.repository.VoiceAssetMapper;
import com.echoes.voice.domain.voice.repository.VoiceAuditLogMapper;
import com.echoes.voice.domain.voice.repository.VoiceGrantMapper;
import com.echoes.voice.domain.voice.service.IVoiceAssetService;
import com.echoes.voice.domain.voice.service.IVoiceGrantService;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class VoiceGrantServiceImpl implements IVoiceGrantService {

    private static final int DEFAULT_GRANT_EXPIRE_DAYS = 30;

    private final VoiceGrantMapper voiceGrantMapper;
    private final VoiceAssetMapper voiceAssetMapper;
    private final VoiceAuditLogMapper voiceAuditLogMapper;
    private final IVoiceAssetService voiceAssetService;
    private final UserServiceFeignClient userServiceFeignClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    @Transactional(rollbackFor = Exception.class)
    public VoiceGrant createGrant(CreateGrantRequestDTO request, UUID userId) {
        if (!voiceAssetService.isOwner(request.getVoiceAssetId(), userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Only owner can grant voice asset");
        }

        if (request.getGranteeUserId().equals(userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Cannot grant voice to yourself");
        }

        try {
            ResponseEntity<UserServiceFeignClient.FamilyRelationResponse> response =
                    userServiceFeignClient.checkFamilyRelation(
                            userId.toString(),
                            request.getGranteeUserId().toString());

            if (response.getBody() != null && !Boolean.TRUE.equals(response.getBody().getInSameFamily())) {
                throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Can only grant to users in same family");
            }
        } catch (VoiceServiceException e) {
            throw e;
        } catch (Exception e) {
            log.error("Failed to check family relation with user-service: {}", e.getMessage(), e);
            throw new VoiceServiceException(VoiceErrorEnum.SERVICE_UNAVAILABLE, "Family relation check failed, please retry");
        }

        int existingCount = voiceGrantMapper.countByAssetAndGrantee(
                request.getVoiceAssetId(), request.getGranteeUserId(), request.getPermission());
        if (existingCount > 0) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Grant already exists for same permission");
        }

        LocalDateTime effectiveExpiresAt = resolveExpiresAt(request);

        VoiceGrant grant = VoiceGrant.builder()
                .grantId(UUID.randomUUID())
                .voiceAssetId(request.getVoiceAssetId())
                .granteeUserId(request.getGranteeUserId())
                .permission(request.getPermission())
                .expiresAt(effectiveExpiresAt)
                .build();

        voiceGrantMapper.insert(grant);
        log.info("Created voice grant: grantId={}, voiceAssetId={}, granteeUserId={}",
                grant.getGrantId(), grant.getVoiceAssetId(), grant.getGranteeUserId());

        writeAuditLog(request.getVoiceAssetId(), userId, "GRANT", "ALLOWED",
                String.format("Grant to user %s, permission=%s, expiresAt=%s, permanent=%s",
                        request.getGranteeUserId(),
                        request.getPermission(),
                        effectiveExpiresAt,
                        Boolean.TRUE.equals(request.getPermanent())));

        return grant;
    }

    @Override
    public List<VoiceGrant> listGivenGrants(UUID userId) {
        List<VoiceAsset> userAssets = voiceAssetMapper.selectByOwnerUserId(userId);
        return userAssets.stream()
                .flatMap(asset -> voiceGrantMapper.selectByVoiceAssetId(asset.getVoiceAssetId()).stream())
                .toList();
    }

    @Override
    public List<VoiceGrant> listReceivedGrants(UUID userId) {
        return voiceGrantMapper.selectValidGrantsByUserId(userId, LocalDateTime.now());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void revokeGrant(UUID grantId, UUID userId) {
        VoiceGrant grant = voiceGrantMapper.selectById(grantId);
        if (grant == null) {
            throw new VoiceServiceException(VoiceErrorEnum.PARAM_VALIDATION_FAILED, "Grant does not exist");
        }

        VoiceAsset asset = voiceAssetMapper.selectById(grant.getVoiceAssetId());
        if (asset == null) {
            throw new VoiceServiceException(VoiceErrorEnum.VOICE_ASSET_NOT_FOUND, "Voice asset does not exist");
        }

        if (!asset.getOwnerUserId().equals(userId)) {
            throw new VoiceServiceException(VoiceErrorEnum.PERMISSION_DENIED, "Only owner can revoke grant");
        }

        voiceGrantMapper.deleteById(grantId);
        log.info("Revoked voice grant: grantId={}, voiceAssetId={}", grantId, grant.getVoiceAssetId());

        writeAuditLog(grant.getVoiceAssetId(), userId, "REVOKE", "ALLOWED",
                String.format("Revoke grant for user %s", grant.getGranteeUserId()));
    }

    @Override
    public boolean hasPermission(UUID voiceAssetId, UUID userId) {
        if (voiceAssetService.isOwner(voiceAssetId, userId)) {
            return true;
        }

        List<VoiceGrant> grants = voiceGrantMapper.selectValidGrantsByUserId(userId, LocalDateTime.now());
        return grants.stream().anyMatch(grant -> grant.getVoiceAssetId().equals(voiceAssetId));
    }

    private void writeAuditLog(UUID voiceAssetId, UUID userId, String action, String result, String details) {
        try {
            VoiceAuditLog auditLog = VoiceAuditLog.builder()
                    .auditId(UUID.randomUUID())
                    .voiceAssetId(voiceAssetId)
                    .actorUserId(userId)
                    .action(action)
                    .result(result)
                    .details(buildAuditDetails(action, result, details))
                    .ts(LocalDateTime.now())
                    .build();
            voiceAuditLogMapper.insert(auditLog);
        } catch (Exception e) {
            log.error("Failed to write voice audit log: voiceAssetId={}, action={}", voiceAssetId, action, e);
        }
    }

    private String buildAuditDetails(String action, String result, String summary) {
        try {
            Map<String, Object> details = new LinkedHashMap<>();
            details.put("action", action);
            details.put("result", result);
            details.put("summary", summary);
            details.put("timestamp", LocalDateTime.now().toString());
            return objectMapper.writeValueAsString(details);
        } catch (Exception e) {
            log.warn("Failed to serialize audit details, fallback to plain text", e);
            return summary;
        }
    }

    private LocalDateTime resolveExpiresAt(CreateGrantRequestDTO request) {
        if (Boolean.TRUE.equals(request.getPermanent())) {
            return null;
        }
        if (request.getExpiresAt() != null) {
            return request.getExpiresAt();
        }
        return LocalDateTime.now().plusDays(DEFAULT_GRANT_EXPIRE_DAYS);
    }
}
