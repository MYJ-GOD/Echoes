package com.echoes.user.domain.user.repository;

import com.echoes.user.domain.user.entity.po.Family;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.UUID;

/**
 * 家庭 Mapper 接口
 * 
 * @author echoes
 */
@Mapper
public interface FamilyMapper {

    int insert(Family family);

    Family selectById(@Param("familyId") UUID familyId);

    /**
     * 查询用户拥有的家庭
     */
    List<Family> selectByOwnerUserId(@Param("ownerUserId") UUID ownerUserId);

    /**
     * 查询用户所属的有效家庭（作为家庭成员）
     */
    List<Family> selectByMemberUserId(@Param("userId") UUID userId);

    /**
     * 查询用户所有有效家庭（拥有或成员）
     */
    List<Family> selectValidByUserId(@Param("userId") UUID userId);

    int update(Family family);

    int softDelete(@Param("familyId") UUID familyId, @Param("deletedAt") java.time.LocalDateTime deletedAt);

    int countByOwner(@Param("ownerUserId") UUID ownerUserId);
}

