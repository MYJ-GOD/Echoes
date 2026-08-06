package com.echoes.user.domain.user.entity.po;

import com.echoes.user.domain.user.enums.UserStatus;
import com.echoes.user.domain.user.enums.UserType;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 用户表实体 (Schema v3)
 * 对应 core_user 表
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CoreUser implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 用户ID (BINARY(16))
     */
    private UUID userId;

    /**
     * 用户类型 (elder/child/normal)
     */
    private UserType userType;

    /**
     * 用户名 (Display name)
     */
    private String name;

    /**
     * 手机号 (Optional in schema, but critical for business)
     */
    private String phoneNumber;

    /**
     * 邮箱 (Optional)
     */
    private String email;

    /**
     * 头像地址
     */
    private String avatarUrl;

    /**
     * 用户状态
     */
    private UserStatus status;

    /**
     * 软删除时间 (v3 preferred)
     */
    private LocalDateTime deletedAt;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    private LocalDateTime updateTime;
}
