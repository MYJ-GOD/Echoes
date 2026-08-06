package com.echoes.user.domain.user.service.impl;

import com.echoes.user.common.constants.MessageConstant;
import com.echoes.user.common.exception.AccountNotFoundException;
import com.echoes.user.common.exception.PasswordErrorException;
import com.echoes.user.domain.user.entity.dto.ChangePasswordDTO;
import com.echoes.user.domain.user.entity.dto.UpdateUserDTO;
import com.echoes.user.domain.user.entity.po.CoreUser;
import com.echoes.user.domain.user.entity.vo.UserVO;
import com.echoes.user.domain.user.repository.UserMapper;
import com.echoes.user.domain.user.service.IUserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

/**
 * 用户服务实现类
 * 提供用户信息查询和更新功能
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements IUserService {

    private final UserMapper userMapper;

    /**
     * 根据ID获取用户信息
     *
     * @param userId 用户ID
     * @return 用户视图对象
     */
    @Override
    @Transactional(readOnly = true)
    public UserVO getUserById(java.util.UUID userId) {
        CoreUser user = userMapper.selectById(userId);
        if (user == null) {
            log.warn("用户不存在: userId={}", userId);
            throw new AccountNotFoundException("用户不存在");
        }

        UserVO userVO = new UserVO();
        BeanUtils.copyProperties(user, userVO);
        userVO.setUserId(user.getUserId().toString());
        return userVO;
    }

    /**
     * 更新用户信息
     *
     * @param userId    用户ID
     * @param updateDTO 更新参数
     * @return 更新后的用户视图对象
     */
    @Override
    @Transactional
    public UserVO updateUser(java.util.UUID userId, UpdateUserDTO updateDTO) {
        CoreUser user = userMapper.selectById(userId);
        if (user == null) {
            log.warn("用户不存在: userId={}", userId);
            throw new AccountNotFoundException("用户不存在");
        }

        // 检查账号（name）是否与其他用户重复
        if (updateDTO.getName() != null && !updateDTO.getName().trim().isEmpty()) {
            String newName = updateDTO.getName().trim();
            // 如果新账号与当前账号不同，检查是否重复
            if (!newName.equals(user.getName())) {
                CoreUser existingUser = userMapper.selectByName(newName);
                if (existingUser != null && !existingUser.getUserId().equals(userId)) {
                    log.warn("账号已存在: name={}, userId={}", newName, userId);
                    throw new AccountNotFoundException("该账号已被使用，请更换其他账号");
                }
            }
            user.setName(newName);
        }

        // 检查电话号是否与其他用户重复
        if (updateDTO.getPhoneNumber() != null && !updateDTO.getPhoneNumber().trim().isEmpty()) {
            String newPhoneNumber = updateDTO.getPhoneNumber().trim();
            // 如果新电话号与当前电话号不同，检查是否重复
            if (!newPhoneNumber.equals(user.getPhoneNumber())) {
                CoreUser existingUser = userMapper.selectByPhoneNumber(newPhoneNumber);
                if (existingUser != null && !existingUser.getUserId().equals(userId)) {
                    log.warn("电话号已存在: phoneNumber={}, userId={}", newPhoneNumber, userId);
                    throw new AccountNotFoundException("该电话号已被使用，请更换其他电话号");
                }
            }
            user.setPhoneNumber(newPhoneNumber);
        }

        // 检查邮箱是否与其他用户重复
        if (updateDTO.getEmail() != null && !updateDTO.getEmail().trim().isEmpty()) {
            String newEmail = updateDTO.getEmail().trim();
            // 如果新邮箱与当前邮箱不同，检查是否重复
            if (!newEmail.equals(user.getEmail())) {
                CoreUser existingUser = userMapper.selectByEmail(newEmail);
                if (existingUser != null && !existingUser.getUserId().equals(userId)) {
                    log.warn("邮箱已存在: email={}, userId={}", newEmail, userId);
                    throw new AccountNotFoundException("该邮箱已被使用，请更换其他邮箱");
                }
            }
            user.setEmail(newEmail);
        }

        userMapper.update(user);

        // 返回更新后的用户信息
        UserVO userVO = new UserVO();
        BeanUtils.copyProperties(user, userVO);
        userVO.setUserId(user.getUserId().toString());
        return userVO;
    }
}

