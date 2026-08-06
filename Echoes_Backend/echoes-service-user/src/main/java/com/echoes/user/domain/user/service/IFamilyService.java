package com.echoes.user.domain.user.service;

import com.echoes.user.domain.user.entity.po.Family;
import com.echoes.user.domain.user.entity.po.FamilyMember;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 家庭服务接口
 * 
 * @author echoes
 */
public interface IFamilyService {

    /**
     * 创建家庭（房主自动成为成员）
     * 
     * @param name 家庭名称
     * @param ownerUserId 房主用户ID
     * @return 创建的家庭
     */
    Family createFamily(String name, UUID ownerUserId);

    /**
     * 获取家庭详情
     * 
     * @param familyId 家庭ID
     * @return 家庭信息
     */
    Family getById(UUID familyId);

    /**
     * 获取用户拥有的家庭列表
     * 
     * @param userId 用户ID
     * @return 家庭列表
     */
    List<Family> listByOwner(UUID userId);

    /**
     * 获取用户所属的家庭列表（作为成员）
     * 
     * @param userId 用户ID
     * @return 家庭列表
     */
    List<Family> listByMember(UUID userId);

    /**
     * 获取用户所有家庭（拥有或成员）
     * 
     * @param userId 用户ID
     * @return 家庭列表
     */
    List<Family> listByUser(UUID userId);

    /**
     * 更新家庭名称
     * 
     * @param familyId 家庭ID
     * @param name 新名称
     * @param operatorUserId 操作人ID
     */
    void updateFamilyName(UUID familyId, String name, UUID operatorUserId);

    /**
     * 解散家庭（删除家庭和所有成员）
     * 
     * @param familyId 家庭ID
     * @param operatorUserId 操作人ID（必须是房主）
     */
    void dissolveFamily(UUID familyId, UUID operatorUserId);

    // ==================== 家庭成员管理 ====================

    /**
     * 添加家庭成员
     * 
     * @param familyId 家庭ID
     * @param userId 要添加的用户ID
     * @param role 角色
     * @param operatorUserId 操作人ID
     * @return 添加的成员记录
     */
    FamilyMember addMember(UUID familyId, UUID userId, String role, UUID operatorUserId);

    /**
     * 移除家庭成员
     * 
     * @param familyId 家庭ID
     * @param userId 要移除的用户ID
     * @param operatorUserId 操作人ID
     */
    void removeMember(UUID familyId, UUID userId, UUID operatorUserId);

    /**
     * 更新成员角色
     * 
     * @param familyId 家庭ID
     * @param userId 用户ID
     * @param role 新角色
     * @param operatorUserId 操作人ID
     */
    void updateMemberRole(UUID familyId, UUID userId, String role, UUID operatorUserId);

    /**
     * 获取家庭所有成员
     * 
     * @param familyId 家庭ID
     * @return 成员列表
     */
    List<FamilyMember> listMembers(UUID familyId);

    /**
     * 获取用户在指定家庭的信息
     * 
     * @param familyId 家庭ID
     * @param userId 用户ID
     * @return 成员信息
     */
    FamilyMember getMember(UUID familyId, UUID userId);

    // ==================== 家庭关系查询 ====================

    /**
     * 检查用户是否在指定家庭中
     * 
     * @param familyId 家庭ID
     * @param userId 用户ID
     * @return 是否在家庭中
     */
    boolean isInFamily(UUID familyId, UUID userId);

    /**
     * 检查两个用户是否在同一家庭
     * 
     * @param userId1 用户1
     * @param userId2 用户2
     * @return 是否在同一家庭，返回家庭ID
     */
    Optional<UUID> findCommonFamilyId(UUID userId1, UUID userId2);

    /**
     * 检查两个用户是否在同一家庭
     * 
     * @param userId1 用户1
     * @param userId2 用户2
     * @return 是否在同一家庭
     */
    boolean isInSameFamily(UUID userId1, UUID userId2);
}

