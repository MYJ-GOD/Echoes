package com.echoes.voice.domain.voice.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.echoes.context.BaseContext;
import com.echoes.voice.common.exception.VoiceServiceException;
import com.echoes.voice.domain.voice.entity.dto.CreateVoiceAssetRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.UpdateVoiceAssetRequestDTO;
import com.echoes.voice.domain.voice.entity.dto.VoiceAssetQueryDTO;
import com.echoes.voice.domain.voice.entity.dto.query.VoiceListQueryRequest;
import com.echoes.voice.domain.voice.entity.dto.query.AssetQueryRequest;
import com.echoes.voice.domain.voice.entity.dto.query.AssetOperationRequest;
import com.echoes.voice.domain.voice.entity.vo.VoiceAssetVO;
import com.echoes.voice.domain.voice.enums.VoiceErrorEnum;
import com.echoes.voice.domain.voice.service.IVoiceAssetService;
import com.echoes.voice.domain.voice.repository.UserVoiceLinkMapper;
import com.echoes.voice.domain.voice.entity.po.UserVoiceLink;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * 音色资产控制器
 * 提供音色资产生命周期管理接口
 */
@Tag(name = "音色资产管理", description = "音色资产的创建、查询、更新、删除等接口")
@RestController
@RequestMapping("/voice/assets")
@RequiredArgsConstructor
@Slf4j
public class VoiceAssetController {

    private final IVoiceAssetService voiceAssetService;
    private final UserVoiceLinkMapper userVoiceLinkMapper;

    /**
     * 创建音色资产
     */
    @Operation(summary = "创建音色资产", description = "上传参考音频并创建音色资产，自动发起训练任务")
    @ApiResponses({
        @ApiResponse(responseCode = "201", description = "创建成功"),
        @ApiResponse(responseCode = "400", description = "请求参数错误"),
        @ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    @PostMapping
    public ResponseEntity<ResponseResult<VoiceAssetVO>> createVoiceAsset(
            @Valid @RequestBody CreateVoiceAssetRequestDTO request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            VoiceAssetVO result = voiceAssetService.createVoiceAsset(request, userUuid);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(ResponseResult.success(result));
        } catch (VoiceServiceException e) {
            log.error("创建音色资产失败: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("创建音色资产异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("创建音色资产失败: " + e.getMessage()));
        }
    }

    /**
     * 查询用户音色列表
     */
    @Operation(summary = "查询用户音色列表", description = "分页查询当前用户的音色资产列表")
    @GetMapping
    public ResponseEntity<ResponseResult<Page<VoiceAssetVO>>> listUserVoices(@ModelAttribute VoiceListQueryRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            VoiceAssetQueryDTO query = VoiceAssetQueryDTO.builder()
                    .status(request.getStatus())
                    .role(request.getRole())
                    .pageNum(request.getPageNum())
                    .pageSize(request.getPageSize())
                    .build();
            Page<VoiceAssetVO> result = voiceAssetService.listUserVoices(userUuid, query);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (Exception e) {
            log.error("查询音色列表异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("查询失败: " + e.getMessage()));
        }
    }

    /**
     * 获取音色详情
     */
    @Operation(summary = "获取音色详情", description = "获取指定音色资产的详细信息")
    @GetMapping("/{voiceAssetId}")
    public ResponseEntity<ResponseResult<VoiceAssetVO>> getVoiceAsset(@ModelAttribute AssetQueryRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            UUID assetUuid = UUID.fromString(request.getVoiceAssetId());
            VoiceAssetVO result = voiceAssetService.getVoiceAsset(assetUuid, userUuid);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的音色资产ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("获取音色详情异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("查询失败: " + e.getMessage()));
        }
    }

    /**
     * 更新音色信息
     */
    @Operation(summary = "更新音色信息", description = "更新音色资产的名称、角色、标签等基本信息")
    @PutMapping("/{voiceAssetId}")
    public ResponseEntity<ResponseResult<VoiceAssetVO>> updateVoiceAsset(
            @Parameter(description = "音色资产ID") @PathVariable("voiceAssetId") String voiceAssetId,
            @Valid @RequestBody UpdateVoiceAssetRequestDTO request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            UUID assetUuid = UUID.fromString(voiceAssetId);
            VoiceAssetVO result = voiceAssetService.updateVoiceAsset(assetUuid, request, userUuid);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的音色资产ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("更新音色信息异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("更新失败: " + e.getMessage()));
        }
    }

    /**
     * 删除音色
     */
    @Operation(summary = "删除音色", description = "软删除指定的音色资产")
    @DeleteMapping("/{voiceAssetId}")
    public ResponseEntity<ResponseResult<Void>> deleteVoiceAsset(
            @Parameter(description = "闊宠壊璧勪骇ID") @PathVariable("voiceAssetId") String voiceAssetId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            UUID assetUuid = UUID.fromString(voiceAssetId);
            voiceAssetService.deleteVoiceAsset(assetUuid, userUuid);
            return ResponseEntity.ok(ResponseResult.success(null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的音色资产ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("删除音色异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("删除失败: " + e.getMessage()));
        }
    }

    /**
     * 设置默认音色
     */
    @Operation(summary = "设置默认音色", description = "将指定音色设为用户的默认音色")
    @PutMapping("/{voiceAssetId}/default")
    public ResponseEntity<ResponseResult<Void>> setDefaultVoice(@ModelAttribute AssetOperationRequest request) {
        try {
            UUID userUuid = getUserId(request.getUserId());
            UUID assetUuid = UUID.fromString(request.getVoiceAssetId());
            voiceAssetService.setDefaultVoice(assetUuid, userUuid);
            return ResponseEntity.ok(ResponseResult.success(null));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error("无效的音色资产ID格式"));
        } catch (VoiceServiceException e) {
            return ResponseEntity.status(HttpStatus.FORBIDDEN)
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("设置默认音色异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("设置失败: " + e.getMessage()));
        }
    }

    /**
     * 获取可用音色列表（自己的 + 收到的分享）
     */
    @Operation(summary = "获取可用音色列表", description = "获取当前用户可用的音色列表，包括自己创建的和他分享的")
    @GetMapping("/available")
    public ResponseEntity<ResponseResult<List<VoiceAssetVO>>> getAvailableVoices(
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        try {
            UUID userUuid = getUserId(userId);
            List<VoiceAssetVO> result = voiceAssetService.getAvailableVoices(userUuid);
            return ResponseEntity.ok(ResponseResult.success(result));
        } catch (VoiceServiceException e) {
            log.error("获取可用音色列表失败: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .body(ResponseResult.error(e.getMessage()));
        } catch (Exception e) {
            log.error("获取可用音色列表异常", e);
            return ResponseEntity.internalServerError()
                    .body(ResponseResult.error("获取失败: " + e.getMessage()));
        }
    }
    /**
     * 【Internal API】获取用户默认音色
     * 供 conversation 服务调用，获取用户级默认音色
     */
    @Operation(summary = "获取用户默认音色", description = "获取用户设置的默认音色资产 ID")
    @GetMapping("/internal/voice/users/{userId}/default-voice")
    public ResponseEntity<UUID> getUserDefaultVoice(@PathVariable("userId") UUID userId) {
        try {
            UserVoiceLink link = userVoiceLinkMapper.selectDefaultByUserId(userId);
            if (link != null && link.getIsDefault() == 1 && link.getIsDeleted() == null) {
                return ResponseEntity.ok(link.getVoiceAssetId());
            }
            return ResponseEntity.notFound().build();
        } catch (Exception e) {
            log.error("获取用户默认音色失败，userId={}", userId, e);
            return ResponseEntity.internalServerError().build();
        }
    }


    /**
     * 获取用户ID
     */
    private UUID getUserId(String userId) {
        // 1. 优先从 BaseContext 获取（UserContextFilter 已从网关注入的 X-USER-ID 设置）
        Object currentId = BaseContext.getCurrentId();
        if (currentId instanceof UUID) {
            return (UUID) currentId;
        }

        // 2. Fallback: 客户端传入（开发环境/旧客户端兼容）
        if (userId != null && !userId.isBlank()) {
            try {
                return UUID.fromString(userId);
            } catch (IllegalArgumentException e) {
                log.warn("getUserId fallback: 无效的 userId 格式: {}", userId);
            }
        }

        throw new VoiceServiceException(VoiceErrorEnum.USER_ID_REQUIRED, "用户ID不能为空");
    }

    /**
     * 统一API响应
     */
    @Data
    public static class ResponseResult<T> {
        private Integer code;
        private String message;
        private T data;

        public static <T> ResponseResult<T> success(T data) {
            ResponseResult<T> response = new ResponseResult<>();
            response.setCode(200);
            response.setMessage("success");
            response.setData(data);
            return response;
        }

        public static <T> ResponseResult<T> error(String message) {
            ResponseResult<T> response = new ResponseResult<>();
            response.setCode(500);
            response.setMessage(message);
            return response;
        }
    }
}

