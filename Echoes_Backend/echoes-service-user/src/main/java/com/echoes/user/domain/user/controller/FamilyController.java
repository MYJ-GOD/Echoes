package com.echoes.user.domain.user.controller;

import com.echoes.context.BaseContext;
import com.echoes.exception.BusinessException;
import com.echoes.user.domain.user.entity.po.Family;
import com.echoes.user.domain.user.entity.po.FamilyMember;
import com.echoes.user.domain.user.service.IFamilyService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * 家庭管理控制器
 * 提供家庭创建、成员管理、关系查询等接口
 */
@Tag(name = "家庭管理", description = "家庭创建、成员管理、关系查询等接口")
@RestController
@RequestMapping("/family")
@RequiredArgsConstructor
public class FamilyController {

    private final IFamilyService familyService;

    /**
     * 创建家庭
     *
     * @param request 创建家庭请求
     * @param userId  用户ID（从请求头获取）
     * @return 创建的家庭信息
     */
    @Operation(summary = "创建家庭", description = "创建一个新家庭，创建者自动成为房主")
    @ApiResponses({
        @ApiResponse(responseCode = "201", description = "创建成功"),
        @ApiResponse(responseCode = "400", description = "请求参数错误"),
        @ApiResponse(responseCode = "500", description = "服务器内部错误")
    })
    @PostMapping
    public ResponseEntity<ResponseResult<FamilyVO>> createFamily(
            @Valid @RequestBody CreateFamilyRequest request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        UUID userUuid = getUserId(userId);
        Family family = familyService.createFamily(request.getName(), userUuid);
        return ResponseEntity.ok(ResponseResult.success(convertToVO(family)));
    }

    /**
     * 获取家庭详情
     *
     * @param familyId 家庭ID
     * @return 家庭详细信息
     */
    @Operation(summary = "获取家庭详情")
    @GetMapping("/{familyId}")
    public ResponseEntity<ResponseResult<FamilyVO>> getFamily(@PathVariable String familyId) {
        UUID familyUuid = UUID.fromString(familyId);
        Family family = familyService.getById(familyUuid);
        if (family == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(ResponseResult.success(convertToVO(family)));
    }

    /**
     * 获取我的家庭列表
     */
    @Operation(summary = "获取我的家庭列表", description = "获取用户拥有或所属的所有家庭")
    @GetMapping("/my")
    public ResponseEntity<ResponseResult<List<FamilyVO>>> listMyFamilies(
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        UUID userUuid = getUserId(userId);
        List<Family> families = familyService.listByUser(userUuid);
        return ResponseEntity.ok(ResponseResult.success(families.stream().map(this::convertToVO).toList()));
    }

    /**
     * 获取家庭成员列表
     */
    @Operation(summary = "获取家庭成员列表")
    @GetMapping("/{familyId}/members")
    public ResponseEntity<ResponseResult<List<FamilyMemberVO>>> listMembers(@PathVariable String familyId) {
        UUID familyUuid = UUID.fromString(familyId);
        List<FamilyMember> members = familyService.listMembers(familyUuid);
        return ResponseEntity.ok(ResponseResult.success(members.stream().map(this::convertToMemberVO).toList()));
    }

    /**
     * 添加家庭成员
     */
    @Operation(summary = "添加家庭成员", description = "家庭成员可以邀请新成员加入")
    @ApiResponses({
        @ApiResponse(responseCode = "201", description = "添加成功"),
        @ApiResponse(responseCode = "400", description = "请求参数错误"),
        @ApiResponse(responseCode = "403", description = "无权限")
    })
    @PostMapping("/{familyId}/members")
    public ResponseEntity<ResponseResult<FamilyMemberVO>> addMember(
            @PathVariable String familyId,
            @Valid @RequestBody AddMemberRequest request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        UUID familyUuid = UUID.fromString(familyId);
        UUID operatorUuid = getUserId(userId);
        FamilyMember member = familyService.addMember(familyUuid, request.getUserId(), request.getRole(), operatorUuid);
        return ResponseEntity.ok(ResponseResult.success(convertToMemberVO(member)));
    }

    /**
     * 移除家庭成员
     */
    @Operation(summary = "移除家庭成员", description = "房主可以移除其他成员，成员可自己退出")
    @DeleteMapping("/{familyId}/members/{targetUserId}")
    public ResponseEntity<ResponseResult<Void>> removeMember(
            @PathVariable String familyId,
            @PathVariable String targetUserId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        UUID familyUuid = UUID.fromString(familyId);
        UUID operatorUuid = getUserId(userId);
        UUID targetUuid = UUID.fromString(targetUserId);
        familyService.removeMember(familyUuid, targetUuid, operatorUuid);
        return ResponseEntity.ok(ResponseResult.success(null));
    }

    /**
     * 更新家庭名称
     */
    @Operation(summary = "更新家庭名称", description = "只有房主可以修改家庭名称")
    @PutMapping("/{familyId}/name")
    public ResponseEntity<ResponseResult<Void>> updateFamilyName(
            @PathVariable String familyId,
            @Valid @RequestBody UpdateFamilyNameRequest request,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        UUID familyUuid = UUID.fromString(familyId);
        UUID operatorUuid = getUserId(userId);
        familyService.updateFamilyName(familyUuid, request.getName(), operatorUuid);
        return ResponseEntity.ok(ResponseResult.success(null));
    }

    /**
     * 解散家庭
     */
    @Operation(summary = "解散家庭", description = "只有房主可以解散家庭，解散后所有成员自动退出")
    @DeleteMapping("/{familyId}")
    public ResponseEntity<ResponseResult<Void>> dissolveFamily(
            @PathVariable String familyId,
            @RequestHeader(value = "X-USER-ID", required = false) String userId) {
        UUID familyUuid = UUID.fromString(familyId);
        UUID operatorUuid = getUserId(userId);
        familyService.dissolveFamily(familyUuid, operatorUuid);
        return ResponseEntity.ok(ResponseResult.success(null));
    }

    /**
     * 检查是否在同一家庭
     */
    @Operation(summary = "检查是否在同一家庭", description = "检查两个用户是否属于同一个家庭")
    @GetMapping("/check-relation")
    public ResponseEntity<ResponseResult<FamilyRelationVO>> checkRelation(
            @RequestParam String userId1,
            @RequestParam String userId2) {
        UUID id1 = UUID.fromString(userId1);
        UUID id2 = UUID.fromString(userId2);
        var commonFamilyId = familyService.findCommonFamilyId(id1, id2);
        FamilyRelationVO vo = FamilyRelationVO.builder()
                .inSameFamily(commonFamilyId.isPresent())
                .commonFamilyId(commonFamilyId.orElse(null))
                .build();
        return ResponseEntity.ok(ResponseResult.success(vo));
    }

    /**
     * 检查用户是否在指定家庭中（供其他服务调用）
     */
    @Operation(summary = "检查用户是否在家庭中", description = "检查指定用户是否在指定家庭中")
    @GetMapping("/{familyId}/members/{userId}/check")
    public ResponseEntity<ResponseResult<Boolean>> checkMember(
            @PathVariable String familyId,
            @PathVariable String userId) {
        UUID familyUuid = UUID.fromString(familyId);
        UUID userUuid = UUID.fromString(userId);
        boolean isInFamily = familyService.isInFamily(familyUuid, userUuid);
        return ResponseEntity.ok(ResponseResult.success(isInFamily));
    }

    // ==================== 辅助方法 ====================

    private UUID getUserId(String userId) {
        if (userId != null && !userId.isBlank()) {
            try {
                return UUID.fromString(userId);
            } catch (IllegalArgumentException e) {
                // 继续尝试从 BaseContext 获取
            }
        }
        Object currentId = BaseContext.getCurrentId();
        if (currentId instanceof UUID) {
            return (UUID) currentId;
        }
        throw new BusinessException("用户ID不能为空");
    }

    private FamilyVO convertToVO(Family family) {
        return FamilyVO.builder()
                .familyId(family.getFamilyId())
                .name(family.getName())
                .ownerUserId(family.getOwnerUserId())
                .createTime(family.getCreateTime())
                .build();
    }

    private FamilyMemberVO convertToMemberVO(FamilyMember member) {
        return FamilyMemberVO.builder()
                .id(member.getId())
                .familyId(member.getFamilyId())
                .userId(member.getUserId())
                .role(member.getRole())
                .createTime(member.getCreateTime())
                .build();
    }

    // ==================== 请求/响应 DTO ====================

    /**
     * 创建家庭请求
     */
    @Data
    @Schema(description = "创建家庭请求")
    public static class CreateFamilyRequest {
        @NotBlank(message = "家庭名称不能为空")
        @Schema(description = "家庭名称", example = "张家")
        private String name;
    }

    /**
     * 添加家庭成员请求
     */
    @Data
    @Schema(description = "添加家庭成员请求")
    public static class AddMemberRequest {
        @Schema(description = "用户 ID", required = true)
        private UUID userId;
        @Schema(description = "成员角色 (PARENT/CHILD/CAREGIVER/OTHER)", example = "CHILD")
        private String role;
    }

    /**
     * 更新家庭名称请求
     */
    @Data
    @Schema(description = "更新家庭名称请求")
    public static class UpdateFamilyNameRequest {
        @NotBlank(message = "家庭名称不能为空")
        @Schema(description = "家庭名称", example = "李家")
        private String name;
    }

    /**
     * 家庭视图对象
     */
    @Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    @Schema(description = "家庭视图对象")
    public static class FamilyVO {
        @Schema(description = "家庭 ID")
        private UUID familyId;
        @Schema(description = "家庭名称")
        private String name;
        @Schema(description = "房主用户 ID")
        private UUID ownerUserId;
        @Schema(description = "创建时间")
        private java.time.LocalDateTime createTime;
    }

    /**
     * 家庭成员视图对象
     */
    @Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    @Schema(description = "家庭成员视图对象")
    public static class FamilyMemberVO {
        @Schema(description = "成员 ID")
        private UUID id;
        @Schema(description = "家庭 ID")
        private UUID familyId;
        @Schema(description = "用户 ID")
        private UUID userId;
        @Schema(description = "成员角色")
        private String role;
        @Schema(description = "加入时间")
        private java.time.LocalDateTime createTime;
    }

    /**
     * 家庭关系视图对象
     */
    @Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    @Schema(description = "家庭关系视图对象")
    public static class FamilyRelationVO {
        @Schema(description = "是否在同一家庭")
        private Boolean inSameFamily;
        @Schema(description = "共同家庭 ID")
        private UUID commonFamilyId;
    }

    /**
     * 统一响应结果
     */
    @Data
    @Schema(description = "统一响应结果")
    public static class ResponseResult<T> {
        @Schema(description = "响应码")
        private Integer code;
        @Schema(description = "响应消息")
        private String message;
        @Schema(description = "响应数据")
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

