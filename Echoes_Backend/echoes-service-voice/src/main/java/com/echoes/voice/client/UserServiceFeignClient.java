package com.echoes.voice.client;

import com.echoes.voice.config.FeignConfig;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.UUID;

/**
 * 用户服务 Feign 客户端
 * 用于调用 echoes-service-user 服务的家庭相关接口
 */
@FeignClient(
        name = "echoes-service-user",
        path = "",
        configuration = FeignConfig.class
)
public interface UserServiceFeignClient {

    /**
     * 检查两个用户是否在同一家庭
     * 
     * @param userId1 用户1 ID
     * @param userId2 用户2 ID
     * @return 检查结果，包含是否在同一家庭及家庭ID
     */
    @GetMapping("/family/check-relation")
    ResponseEntity<FamilyRelationResponse> checkFamilyRelation(
            @RequestParam("userId1") String userId1,
            @RequestParam("userId2") String userId2);

    /**
     * 检查用户是否在指定家庭中
     * 
     * @param familyId 家庭ID
     * @param userId 用户ID
     * @return 是否在家庭中
     */
    @GetMapping("/family/{familyId}/members/{userId}/check")
    ResponseEntity<Boolean> isUserInFamily(
            @PathVariable("familyId") String familyId,
            @PathVariable("userId") String userId);

    /**
     * 获取用户在指定家庭的信息
     * 
     * @param familyId 家庭ID
     * @param userId 用户ID
     * @return 成员信息
     */
    @GetMapping("/family/{familyId}/members/{userId}")
    ResponseEntity<FamilyMemberResponse> getFamilyMember(
            @PathVariable("familyId") String familyId,
            @PathVariable("userId") String userId);

    /**
     * 响应 DTOs
     */
    @lombok.Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    public static class FamilyRelationResponse {
        private Boolean inSameFamily;
        private UUID commonFamilyId;
    }

    @lombok.Data
    @lombok.Builder
    @lombok.NoArgsConstructor
    @lombok.AllArgsConstructor
    public static class FamilyMemberResponse {
        private UUID id;
        private UUID familyId;
        private UUID userId;
        private String role;
        private java.time.LocalDateTime createTime;
    }
}

