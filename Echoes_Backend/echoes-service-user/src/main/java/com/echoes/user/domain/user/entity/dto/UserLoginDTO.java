package com.echoes.user.domain.user.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.Data;

/**
 * 用户登录DTO (v3 无密码版)
 * 仅支持手机号登录
 * 
 * @author echoes
 */
@Data
@Schema(description = "用户登录DTO")
public class UserLoginDTO {
    
    @NotBlank(message = "手机号不能为空")
    @Pattern(regexp = "^1[3-9]\\d{9}$", message = "手机号格式不正确")
    @Schema(description = "手机号", example = "13800138000", required = true)
    private String phoneNumber;
    
    // 暂时不校验验证码，但保留字段建议，后续如果要加上可以打开
    // @NotBlank(message = "验证码不能为空")
    // private String verifyCode;
}
