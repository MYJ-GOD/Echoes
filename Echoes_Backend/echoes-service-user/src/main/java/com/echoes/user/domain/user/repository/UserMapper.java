package com.echoes.user.domain.user.repository;

import com.echoes.user.domain.user.entity.po.CoreUser;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.UUID;

/**
 * 用户Mapper接口
 * 
 * @author echoes
 */
@Mapper
public interface UserMapper {
    
    /**
     * 根据用户ID查询用户
     */
    CoreUser selectById(@Param("userId") UUID userId);
    
    /**
     * 根据用户名查询用户
     */
    CoreUser selectByName(@Param("name") String name);
    
    /**
     * 根据手机号查询用户
     */
    CoreUser selectByPhoneNumber(@Param("phoneNumber") String phoneNumber);
    
    /**
     * 根据邮箱查询用户
     */
    CoreUser selectByEmail(@Param("email") String email);
    
    /**
     * 插入用户
     */
    int insert(CoreUser user);
    
    /**
     * 更新用户信息
     */
    int update(CoreUser user);
    
    /**
     * 更新用户状态
     */
    int updateStatus(@Param("userId") UUID userId, @Param("status") String status);
}
