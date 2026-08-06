package com.echoes.user.domain.user.entity.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 修改密码DTO
 * 
 * @author echoes
 */
@Data
@Schema(description = "修改密码DTO")
public class ChangePasswordDTO {
    
    @NotBlank(message = "新密码不能为空")
    @Schema(description = "新密码", example = "newPassword123", required = true)
    private String newPassword;
}

