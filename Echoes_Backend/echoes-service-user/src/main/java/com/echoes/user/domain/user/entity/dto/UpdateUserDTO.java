package com.echoes.user.domain.user.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 更新用户信息DTO
 * 
 * @author echoes
 */
@Data
@Schema(description = "更新用户信息DTO")
public class UpdateUserDTO {
    
    @Schema(description = "用户名（账号）", example = "testuser")
    private String name;
    
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    @Schema(description = "手机号", example = "13800138000")
    private String phoneNumber;
    
    @Pattern(regexp = "^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", message = "邮箱格式不正确")
    @Schema(description = "邮箱", example = "test@example.com")
    private String email;
}

