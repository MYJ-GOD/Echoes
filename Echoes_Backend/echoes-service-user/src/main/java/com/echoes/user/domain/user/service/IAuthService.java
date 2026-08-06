package com.echoes.user.domain.user.service;

import com.echoes.user.domain.user.entity.dto.UserLoginDTO;
import com.echoes.user.domain.user.entity.dto.UserRegisterDTO;
import com.echoes.user.domain.user.entity.vo.UserLoginVO;
import com.echoes.user.domain.user.entity.vo.UserVO;

/**
 * 认证服务接口
 * 
 * @author echoes
 */
public interface IAuthService {
    
    /**
     * 用户登录
     * 
     * @param loginDTO 登录信息
     * @return 登录结果（包含token和用户信息）
     */
    UserLoginVO login(UserLoginDTO loginDTO);
    
    /**
     * 用户注册
     * 
     * @param registerDTO 注册信息
     * @return 注册结果（包含token和用户信息）
     */
    UserLoginVO register(UserRegisterDTO registerDTO);
    
    /**
     * 用户登出
     * 
     * @param token JWT Token
     */
    void logout(String token);
    
    /**
     * 验证Token
     * 
     * @param token JWT Token
     * @return true 表示token有效，false 表示token无效
     */
    boolean validateToken(String token);
    
    /**
     * 刷新Token
     * 
     * @param token 旧Token
     * @return 新的Token
     */
    String refreshToken(String token);
    
    /**
     * 获取当前登录用户信息
     * 
     * @param token JWT Token
     * @return 用户信息
     */
    UserVO getCurrentUser(String token);
}

