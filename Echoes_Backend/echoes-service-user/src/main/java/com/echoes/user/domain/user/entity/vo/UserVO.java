package com.echoes.user.domain.user.entity.vo;

import com.echoes.user.domain.user.enums.UserStatus;
import com.echoes.user.domain.user.enums.UserType;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 用户信息VO
 * 
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "用户信息VO")
public class UserVO {
    
    @Schema(description = "用户ID", example = "1")
    private String userId;
    
    @Schema(description = "用户类型", example = "NORMAL")
    private UserType userType;
    
    @Schema(description = "用户名", example = "testuser")
    private String name;
    
    @Schema(description = "手机号", example = "13800138000")
    private String phoneNumber;
    
    @Schema(description = "邮箱", example = "test@example.com")
    private String email;
    
    @Schema(description = "头像地址", example = "https://example.com/avatar.jpg")
    private String avatarUrl;
    
    @Schema(description = "用户状态", example = "ACTIVE")
    private UserStatus status;
    
    @Schema(description = "创建时间")
    private LocalDateTime createTime;
}

