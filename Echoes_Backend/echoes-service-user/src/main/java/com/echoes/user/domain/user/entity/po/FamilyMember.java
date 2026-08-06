package com.echoes.user.domain.user.entity.po;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 家庭成员表
 * 对应表: family_member
 * 
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FamilyMember {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 记录ID
     */
    private UUID id;

    /**
     * 家庭ID
     */
    private UUID familyId;

    /**
     * 用户ID
     */
    private UUID userId;

    /**
     * 角色：PARENT/CHILD/CAREGIVER/OTHER
     */
    private String role;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}

