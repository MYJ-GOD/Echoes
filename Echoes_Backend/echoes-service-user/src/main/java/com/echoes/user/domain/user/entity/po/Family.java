package com.echoes.user.domain.user.entity.po;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 家庭表
 * 对应表: family
 * 
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Family {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 家庭ID
     */
    private UUID familyId;

    /**
     * 房主用户ID
     */
    private UUID ownerUserId;

    /**
     * 家庭名称
     */
    private String name;

    /**
     * 是否已删除
     */
    private Integer isDeleted;

    /**
     * 删除时间
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

