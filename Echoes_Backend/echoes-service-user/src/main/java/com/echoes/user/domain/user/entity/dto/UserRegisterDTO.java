package com.echoes.user.domain.user.entity.dto;

import com.echoes.user.domain.user.enums.UserType;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 用户注册DTO (v3 无密码版)
 * 仅需手机号和用户名
 * 
 * @author echoes
 */
@Data
@Schema(description = "用户注册DTO")
public class UserRegisterDTO {
    
    @NotBlank(message = "用户名不能为空")
    @Schema(description = "用户名", example = "testuser", required = true)
    private String name;
    
    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    @Schema(description = "手机号", example = "13800138000", required = true)
    private String phoneNumber;
    
    @Pattern(regexp = "^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$", message = "邮箱格式不正确")
    @Schema(description = "邮箱", example = "test@example.com")
    private String email;
    
    @Schema(description = "用户类型", example = "NORMAL")
    private UserType userType = UserType.NORMAL;
}
