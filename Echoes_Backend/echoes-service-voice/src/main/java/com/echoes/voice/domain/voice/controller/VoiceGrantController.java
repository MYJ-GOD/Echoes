package com.echoes.voice.domain.voice.controller;

import com.echoes.context.BaseContext;
import com.echoes.voice.domain.voice.entity.dto.CreateGrantRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.GrantOperationRequest;
import com.echoes.voice.domain.voice.entity.dto.PermissionCheckRequest;
import com.echoes.voice.domain.voice.entity.po.VoiceGrant;
import com.echoes.voice.domain.voice.entity.vo.VoiceGrantVO;
import com.echoes.voice.domain.voice.service.IVoiceGrantService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 音色分享授权 Controller
 * 提供音色分享、取消分享、分享列表等API
 *
 * @author echoes
 */
@Slf4j
@RestController
@RequestMapping("/internal/voice/grants")
@RequiredArgsConstructor
@Tag(name = "音色分享授权接口")
public class VoiceGrantController {

    private final IVoiceGrantService voiceGrantService;

    /**
     * 统一响应格式
     */
    private static class ResponseResult<T> {
        private Integer code;
        private String message;
        private T data;

        public ResponseResult(Integer code, String message, T data) {
            this.code = code;
            this.message = message;
            this.data = data;
        }

        public static <T> ResponseResult<T> success(T data) {
            return new ResponseResult<>(200, "success", data);
        }

        public static <T> ResponseResult<T> success() {
            return new ResponseResult<>(200, "success", null);
        }

        public static <T> ResponseResult<T> error(String message) {
            return new ResponseResult<>(500, message, null);
        }

        public static <T> ResponseResult<T> error(Integer code, String message) {
            return new ResponseResult<>(code, message, null);
        }
    }

    /**
     * 创建分享授权
     *
     * @param request 创建请求
     * @return 授权信息
     */
    @PostMapping
    @Operation(summary = "创建分享授权")
    public ResponseResult<VoiceGrantVO> createGrant(@RequestBody CreateGrantRequestDTO request) {
        UUID userId = BaseContext.getCurrentId();
        if (userId == null) {
            return ResponseResult.error(401, "用户未登录");
        }

        try {
            VoiceGrant grant = voiceGrantService.createGrant(request, userId);
            return ResponseResult.success(convertToVO(grant));
        } catch (Exception e) {
            log.error("创建分享授权失败: userId={}, request={}", userId, request, e);
            return ResponseResult.error(e.getMessage());
        }
    }

    /**
     * 查询我给出的分享列表
     *
     * @return 分享列表
     */
    @GetMapping("/given")
    @Operation(summary = "查询我给出的分享列表")
    public ResponseResult<List<VoiceGrantVO>> listGivenGrants() {
        UUID userId = BaseContext.getCurrentId();
        if (userId == null) {
            return ResponseResult.error(401, "用户未登录");
        }

        try {
            List<VoiceGrant> grants = voiceGrantService.listGivenGrants(userId);
            List<VoiceGrantVO> voList = grants.stream()
                    .map(this::convertToVO)
                    .collect(Collectors.toList());
            return ResponseResult.success(voList);
        } catch (Exception e) {
            log.error("查询给出的分享列表失败: userId={}", userId, e);
            return ResponseResult.error(e.getMessage());
        }
    }

    /**
     * 查询我收到的分享列表
     *
     * @return 分享列表
     */
    @GetMapping("/received")
    @Operation(summary = "查询我收到的分享列表")
    public ResponseResult<List<VoiceGrantVO>> listReceivedGrants() {
        UUID userId = BaseContext.getCurrentId();
        if (userId == null) {
            return ResponseResult.error(401, "用户未登录");
        }

        try {
            List<VoiceGrant> grants = voiceGrantService.listReceivedGrants(userId);
            List<VoiceGrantVO> voList = grants.stream()
                    .map(this::convertToVO)
                    .collect(Collectors.toList());
            return ResponseResult.success(voList);
        } catch (Exception e) {
            log.error("查询收到的分享列表失败: userId={}", userId, e);
            return ResponseResult.error(e.getMessage());
        }
    }

    /**
     * 取消分享
     *
     * @param request 授权操作请求
     * @return 操作结果
     */
    @DeleteMapping("/{grantId}")
    @Operation(summary = "取消分享")
    public ResponseResult<Void> revokeGrant(@ModelAttribute GrantOperationRequest request) {
        UUID userId = request.getUserId();
        if (userId == null) {
            return ResponseResult.error(401, "用户未登录");
        }

        try {
            voiceGrantService.revokeGrant(request.getGrantId(), userId);
            return ResponseResult.success();
        } catch (Exception e) {
            log.error("取消分享失败: grantId={}, userId={}", request.getGrantId(), userId, e);
            return ResponseResult.error(e.getMessage());
        }
    }

    /**
     * 检查是否有权限使用音色
     *
     * @param request 权限检查请求
     * @return 权限检查结果
     */
    @GetMapping("/check/{voiceAssetId}")
    @Operation(summary = "检查是否有权限使用音色")
    public ResponseResult<Boolean> checkPermission(@ModelAttribute PermissionCheckRequest request) {
        UUID userId = request.getUserId();
        if (userId == null) {
            return ResponseResult.error(401, "用户未登录");
        }

        try {
            boolean hasPermission = voiceGrantService.hasPermission(request.getVoiceAssetId(), userId);
            return ResponseResult.success(hasPermission);
        } catch (Exception e) {
            log.error("检查权限失败: voiceAssetId={}, userId={}", request.getVoiceAssetId(), userId, e);
            return ResponseResult.error(e.getMessage());
        }
    }

    /**
     * 转换Entity到VO
     */
    private VoiceGrantVO convertToVO(VoiceGrant grant) {
        return VoiceGrantVO.builder()
                .grantId(grant.getGrantId())
                .voiceAssetId(grant.getVoiceAssetId())
                .grantorUserId(grant.getGrantorUserId())
                .granteeUserId(grant.getGranteeUserId())
                .permission(grant.getPermission())
                .expiresAt(grant.getExpiresAt())
                .createTime(grant.getCreateTime())
                .build();
    }
}
