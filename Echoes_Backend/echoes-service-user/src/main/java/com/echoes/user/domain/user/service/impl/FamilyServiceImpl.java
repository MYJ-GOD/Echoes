package com.echoes.user.domain.user.service.impl;

import com.echoes.exception.BusinessException;
import com.echoes.user.domain.user.entity.po.Family;
import com.echoes.user.domain.user.entity.po.FamilyMember;
import com.echoes.user.domain.user.enums.FamilyRole;
import com.echoes.user.domain.user.repository.FamilyMapper;
import com.echoes.user.domain.user.repository.FamilyMemberMapper;
import com.echoes.user.domain.user.service.IFamilyService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 家庭服务实现
 *
 * @author echoes
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FamilyServiceImpl implements IFamilyService {

    private final FamilyMapper familyMapper;
    private final FamilyMemberMapper familyMemberMapper;

    @Override
    @Transactional(rollbackFor = BusinessException.class)
    public Family createFamily(String name, UUID ownerUserId) {
        // 1. 创建家庭
        Family family = Family.builder()
                .familyId(UUID.randomUUID())
                .ownerUserId(ownerUserId)
                .name(name)
                .isDeleted(0)
                .build();
        familyMapper.insert(family);
        log.info("创建家庭成功: familyId={}, name={}, ownerUserId={}", 
                family.getFamilyId(), name, ownerUserId);

        // 2. 房主自动成为成员（角色为 PARENT）
        FamilyMember ownerMember = FamilyMember.builder()
                .id(UUID.randomUUID())
                .familyId(family.getFamilyId())
                .userId(ownerUserId)
                .role(FamilyRole.PARENT.name())
                .build();
        familyMemberMapper.insert(ownerMember);
        log.info("房主自动成为家庭成员: familyId={}, userId={}, role={}", 
                family.getFamilyId(), ownerUserId);

        return family;
    }

    @Override
    public Family getById(UUID familyId) {
        return familyMapper.selectById(familyId);
    }

    @Override
    public List<Family> listByOwner(UUID userId) {
        return familyMapper.selectByOwnerUserId(userId);
    }

    @Override
    public List<Family> listByMember(UUID userId) {
        return familyMapper.selectByMemberUserId(userId);
    }

    @Override
    public List<Family> listByUser(UUID userId) {
        return familyMapper.selectValidByUserId(userId);
    }

    @Override
    @Transactional(rollbackFor = BusinessException.class)
    public void updateFamilyName(UUID familyId, String name, UUID operatorUserId) {
        Family family = familyMapper.selectById(familyId);
        if (family == null) {
            throw new BusinessException("家庭不存在");
        }
        if (!family.getOwnerUserId().equals(operatorUserId)) {
            throw new BusinessException("只有房主可以修改家庭名称");
        }
        family.setName(name);
        familyMapper.update(family);
        log.info("更新家庭名称: familyId={}, newName={}", familyId, name);
    }

    @Override
    @Transactional(rollbackFor = BusinessException.class)
    public void dissolveFamily(UUID familyId, UUID operatorUserId) {
        Family family = familyMapper.selectById(familyId);
        if (family == null) {
            throw new BusinessException("家庭不存在");
        }
        if (!family.getOwnerUserId().equals(operatorUserId)) {
            throw new BusinessException("只有房主可以解散家庭");
        }

        // 删除所有成员
        familyMemberMapper.deleteByFamilyId(familyId);
        
        // 软删除家庭
        familyMapper.softDelete(familyId, LocalDateTime.now());
        
        log.info("解散家庭: familyId={}, operatorUserId={}", familyId, operatorUserId);
    }

    @Override
    @Transactional(rollbackFor = BusinessException.class)
    public FamilyMember addMember(UUID familyId, UUID userId, String role, UUID operatorUserId) {
        // 1. 校验家庭存在
        Family family = familyMapper.selectById(familyId);
        if (family == null) {
            throw new BusinessException("家庭不存在");
        }

        // 2. 校验操作人是否有权限（家庭成员即可邀请）
        if (!isInFamily(familyId, operatorUserId)) {
            throw new BusinessException("只有家庭成员可以邀请新成员");
        }

        // 3. 检查用户是否已在家庭中
        if (isInFamily(familyId, userId)) {
            throw new BusinessException("用户已在家庭中");
        }

        // 4. 添加成员
        FamilyMember member = FamilyMember.builder()
                .id(UUID.randomUUID())
                .familyId(familyId)
                .userId(userId)
                .role(role != null ? role : FamilyRole.OTHER.name())
                .build();
        familyMemberMapper.insert(member);
        
        log.info("添加家庭成员: familyId={}, userId={}, role={}, operator={}", 
                familyId, userId, role, operatorUserId);
        
        return member;
    }

    @Override
    @Transactional(rollbackFor = BusinessException.class)
    public void removeMember(UUID familyId, UUID userId, UUID operatorUserId) {
        // 1. 校验操作人是否有权限
        Family family = familyMapper.selectById(familyId);
        if (family == null) {
            throw new BusinessException("家庭不存在");
        }

        // 房主可以移除任何人，成员可以自己退出
        boolean isOwner = family.getOwnerUserId().equals(operatorUserId);
        boolean isSelf = operatorUserId.equals(userId);
        
        if (!isOwner && !isSelf) {
            throw new BusinessException("只有房主可以移除其他成员，或成员可自己退出");
        }

        // 2. 不能移除房主自己
        if (family.getOwnerUserId().equals(userId)) {
            throw new BusinessException("不能移除房主，如需解散家庭请使用解散功能");
        }

        // 3. 移除成员
        familyMemberMapper.deleteByFamilyAndUser(familyId, userId);
        
        log.info("移除家庭成员: familyId={}, userId={}, operator={}", 
                familyId, userId, operatorUserId);
    }

    @Override
    @Transactional(rollbackFor = BusinessException.class)
    public void updateMemberRole(UUID familyId, UUID userId, String role, UUID operatorUserId) {
        // 1. 校验操作人是否有权限（只有房主可以修改角色）
        Family family = familyMapper.selectById(familyId);
        if (family == null) {
            throw new BusinessException("家庭不存在");
        }
        if (!family.getOwnerUserId().equals(operatorUserId)) {
            throw new BusinessException("只有房主可以修改成员角色");
        }

        // 2. 不能修改房主的角色
        if (family.getOwnerUserId().equals(userId)) {
            throw new BusinessException("不能修改房主的角色");
        }

        // 3. 更新角色
        FamilyMember member = familyMemberMapper.selectByFamilyAndUser(familyId, userId);
        if (member == null) {
            throw new BusinessException("成员不存在");
        }
        member.setRole(role);
        familyMemberMapper.update(member);
        
        log.info("更新成员角色: familyId={}, userId={}, newRole={}", familyId, userId, role);
    }

    @Override
    public List<FamilyMember> listMembers(UUID familyId) {
        return familyMemberMapper.selectByFamilyId(familyId);
    }

    @Override
    public FamilyMember getMember(UUID familyId, UUID userId) {
        return familyMemberMapper.selectByFamilyAndUser(familyId, userId);
    }

    @Override
    public boolean isInFamily(UUID familyId, UUID userId) {
        return familyMemberMapper.countByFamilyAndUser(familyId, userId) > 0;
    }

    @Override
    public Optional<UUID> findCommonFamilyId(UUID userId1, UUID userId2) {
        return familyMemberMapper.findCommonFamilyId(userId1, userId2);
    }

    @Override
    public boolean isInSameFamily(UUID userId1, UUID userId2) {
        return findCommonFamilyId(userId1, userId2).isPresent();
    }
}

