package com.echoes.user.domain.user.service;

import com.echoes.user.domain.user.entity.dto.ChangePasswordDTO;
import com.echoes.user.domain.user.entity.dto.UpdateUserDTO;
import com.echoes.user.domain.user.entity.vo.UserVO;

/**
 * 用户服务接口
 * 
 * @author echoes
 */
public interface IUserService {
    
    /**
     * 根据ID获取用户信息
     * 
     * @param userId 用户ID
     * @return 用户信息
     */
    UserVO getUserById(java.util.UUID userId);
    
    /**
     * 更新用户信息
     * 
     * @param userId 用户ID
     * @param updateDTO 更新信息
     * @return 更新后的用户信息
     */
    UserVO updateUser(java.util.UUID userId, UpdateUserDTO updateDTO);
}

