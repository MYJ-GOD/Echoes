package com.echoes.user.domain.user.entity.po;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.io.Serializable;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 用户鉴权表 (Schema v3)
 * 对应 user_auth 表
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserAuth implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 鉴权ID (BINARY(16))
     */
    private UUID authId;

    /**
     * 用户ID (BINARY(16))
     */
    private UUID userId;

    /**
     * 鉴权提供方 (PHONE, WECHAT, etc.)
     */
    private String provider;

    /**
     * 第三方标识 (手机号 or OpenID)
     */
    private String openId;

    /**
     * UnionID (微信等)
     */
    private String unionId;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}
