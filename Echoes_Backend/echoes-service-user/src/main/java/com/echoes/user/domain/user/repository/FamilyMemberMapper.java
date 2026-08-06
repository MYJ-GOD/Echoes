package com.echoes.user.domain.user.repository;

import com.echoes.user.domain.user.entity.po.FamilyMember;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 家庭成员 Mapper 接口
 * 
 * @author echoes
 */
@Mapper
public interface FamilyMemberMapper {

    int insert(FamilyMember member);

    FamilyMember selectById(@Param("id") UUID id);

    /**
     * 查询家庭所有成员
     */
    List<FamilyMember> selectByFamilyId(@Param("familyId") UUID familyId);

    /**
     * 查询用户所属的所有家庭
     */
    List<FamilyMember> selectByUserId(@Param("userId") UUID userId);

    /**
     * 查询用户在指定家庭的成员记录
     */
    FamilyMember selectByFamilyAndUser(@Param("familyId") UUID familyId, @Param("userId") UUID userId);

    /**
     * 检查用户是否在指定家庭中
     */
    int countByFamilyAndUser(@Param("familyId") UUID familyId, @Param("userId") UUID userId);

    /**
     * 检查用户是否在某家庭的成员
     */
    int countByUserId(@Param("userId") UUID userId);

    /**
     * 查询两个用户是否在同一家庭
     */
    Optional<UUID> findCommonFamilyId(@Param("userId1") UUID userId1, @Param("userId2") UUID userId2);

    int update(FamilyMember member);

    int deleteById(@Param("id") UUID id);

    int deleteByFamilyId(@Param("familyId") UUID familyId);

    int deleteByFamilyAndUser(@Param("familyId") UUID familyId, @Param("userId") UUID userId);
}

