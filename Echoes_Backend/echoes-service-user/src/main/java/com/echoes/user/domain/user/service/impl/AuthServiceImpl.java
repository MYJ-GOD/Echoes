package com.echoes.user.domain.user.service.impl;

import com.echoes.user.common.constants.JwtClaimsConstant;
import com.echoes.user.common.constants.LogMessageConstant;
import com.echoes.user.common.constants.MessageConstant;
import com.echoes.user.domain.user.enums.LogMessageEnum;
import com.echoes.user.common.exception.AccountLockedException;
import com.echoes.user.common.exception.AccountNotFoundException;
import com.echoes.user.domain.user.entity.dto.UserLoginDTO;
import com.echoes.user.domain.user.entity.dto.UserRegisterDTO;
import com.echoes.user.domain.user.entity.po.CoreUser;
import com.echoes.user.domain.user.entity.po.UserAuth;
import com.echoes.user.domain.user.entity.vo.UserLoginVO;
import com.echoes.user.domain.user.entity.vo.UserVO;
import com.echoes.user.domain.user.enums.UserStatus;
import com.echoes.user.domain.user.repository.UserAuthMapper;
import com.echoes.user.domain.user.repository.UserMapper;
import com.echoes.user.domain.user.service.IAuthService;
import com.echoes.user.common.util.JwtUtil;
import com.auth0.jwt.interfaces.DecodedJWT;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 认证服务实现类 (v3 无密码版)
 * 提供用户登录、注册、Token管理等功能
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements IAuthService {

    private final UserMapper userMapper;
    private final UserAuthMapper userAuthMapper;
    private final RedisTemplate<String, Object> redisTemplate;
    private final JwtUtil jwtUtil;

    /**
     * 认证提供者类型：手机号
     */
    private static final String PROVIDER_PHONE = "PHONE";

    /**
     * 用户登录
     *
     * @param loginDTO 登录参数
     * @return 登录结果（Token和用户信息）
     */
    @Override
    public UserLoginVO login(UserLoginDTO loginDTO) {
        String phoneNumber = loginDTO.getPhoneNumber();
        
        // 1. 查询鉴权信息 (PHONE provider)
        UserAuth userAuth = userAuthMapper.selectByProviderAndOpenId(PROVIDER_PHONE, phoneNumber);
        
        CoreUser user;
        if (userAuth == null) {
            // 自动注册逻辑（可选）或者抛出用户不存在
            // 根据需求描述："登录时候填写手机号" -> 通常意味着如果不存在则可能是注册或报错
            // 但需求也提到了 "注册时候也是只需要手机号和name"，暗示注册是分开的接口
            // 不过现代APP常采用 "登录即注册" 或 "未注册则引导注册"
            // 这里遵循标准流程：如果未找到Auth，尝试查找CoreUser(可能历史数据)，如果都没有则报错提示注册
            
            // 尝试通过手机号查找 CoreUser (兼容旧数据或容错)
            user = userMapper.selectByPhoneNumber(phoneNumber);
            if (user == null) {
                log.warn("登录失败，用户不存在: {}", phoneNumber);
                throw new AccountNotFoundException("用户不存在，请先注册");
            }
            
            // 补全 Auth 信息 (如果 CoreUser 存在但 Auth 不存在)
            log.info("补全用户鉴权信息: userId={}, phone={}", user.getUserId(), phoneNumber);
            UserAuth newAuth = UserAuth.builder()
                    .authId(UUID.randomUUID())
                    .userId(user.getUserId())
                    .provider(PROVIDER_PHONE)
                    .openId(phoneNumber)
                    .createTime(LocalDateTime.now())
                    .build();
            userAuthMapper.insert(newAuth);
            
        } else {
            // 获取用户信息
            user = userMapper.selectById(userAuth.getUserId());
            if (user == null) {
                // 数据不一致，Auth存在但User不存在（可能被物理删除了？）
                log.error("数据异常: UserAuth存在但CoreUser不存在, userId={}", userAuth.getUserId());
                throw new AccountNotFoundException(MessageConstant.ACCOUNT_NOT_FOUND);
            }
        }
        
        // 2. 检查用户状态
        if (user.getStatus() != UserStatus.ACTIVE) {
            log.warn(LogMessageEnum.LOGIN_FAILED_STATUS_ERROR.getMessage(), user.getUserId(), user.getStatus());
            throw new AccountLockedException(MessageConstant.ACCOUNT_LOCKED);
        }
        
        // 3. 生成JWT Token
        String token = generateToken(user);
        
        log.info(LogMessageEnum.USER_LOGIN_SUCCESS.getMessage(), user.getUserId(), user.getName());
        
        // 4. 返回登录信息
        return UserLoginVO.builder()
            .token(token)
            .user(convertToVO(user))
            .build();
    }

    /**
     * 补全用户鉴权信息（内部方法，带事务）
     */
    @Transactional(rollbackFor = Exception.class)
    protected void repairAuth(CoreUser user, String phoneNumber) {
        log.info("补全用户鉴权信息：userId={}, phone={}", user.getUserId(), phoneNumber);
        UserAuth newAuth = UserAuth.builder()
                .authId(UUID.randomUUID())
                .userId(user.getUserId())
                .provider(PROVIDER_PHONE)
                .openId(phoneNumber)
                .createTime(LocalDateTime.now())
                .build();
        userAuthMapper.insert(newAuth);
    }

    /**
     * 用户注册
     *
     * @param registerDTO 注册参数
     * @return 注册结果（Token和用户信息）
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public UserLoginVO register(UserRegisterDTO registerDTO) {
        String phoneNumber = registerDTO.getPhoneNumber();
        
        // 1. 检查手机号是否已存在 (通过 Auth 表)
        UserAuth existingAuth = userAuthMapper.selectByProviderAndOpenId(PROVIDER_PHONE, phoneNumber);
        if (existingAuth != null) {
            log.warn(LogMessageEnum.REGISTER_FAILED_PHONE_EXISTS.getMessage(), phoneNumber);
            throw new AccountNotFoundException(MessageConstant.ALREADY_EXISTS);
        }
        
        // 2. 再次检查 CoreUser 表 (双重保障)
        CoreUser existingUser = userMapper.selectByPhoneNumber(phoneNumber);
        if (existingUser != null) {
            log.warn("注册失败，手机号已绑定其他用户: {}", phoneNumber);
            // 此时可能是 Auth 数据丢失，尝试修复 Auth 并直接登录？
            // 为安全起见，还是提示已存在
            throw new AccountNotFoundException(MessageConstant.ALREADY_EXISTS);
        }
        
        // 3. 创建新用户
        UUID userId = UUID.randomUUID();
        CoreUser newUser = CoreUser.builder()
                .userId(userId)
                .name(registerDTO.getName())
                .phoneNumber(phoneNumber)
                .email(registerDTO.getEmail())
                .userType(registerDTO.getUserType())
                .status(UserStatus.ACTIVE)
                .createTime(LocalDateTime.now())
                .updateTime(LocalDateTime.now())
                .build();
        
        userMapper.insert(newUser);
        
        // 4. 创建鉴权信息
        UserAuth newAuth = UserAuth.builder()
                .authId(UUID.randomUUID())
                .userId(userId)
                .provider(PROVIDER_PHONE)
                .openId(phoneNumber)
                .createTime(LocalDateTime.now())
                .build();
        
        userAuthMapper.insert(newAuth);
        
        log.info("用户注册成功: userId={}, phone={}", userId, phoneNumber);
        
        // 5. 自动登录，返回 Token
        String token = generateToken(newUser);
        
        return UserLoginVO.builder()
                .token(token)
                .user(convertToVO(newUser))
                .build();
    }

    /**
     * 用户登出
     *
     * @param token JWT Token
     */
    @Override
    public void logout(String token) {
        // JWT 是无状态的，通常由前端丢弃 Token
        // 如果需要服务端注销，可以将 Token 加入 Redis 黑名单
        // 这里暂时只做日志记录
        if (StringUtils.hasText(token)) {
            log.info("用户登出: {}", token.substring(0, Math.min(token.length(), 20)) + "...");
        }
    }

    /**
     * 验证Token是否有效
     *
     * @param token JWT Token
     * @return 是否有效
     */
    @Override
    public boolean validateToken(String token) {
        return jwtUtil.isValidUserToken(token);
    }

    /**
     * 刷新Token
     *
     * @param token 旧JWT Token
     * @return 新的JWT Token，如果验证失败则返回null
     */
    @Override
    public String refreshToken(String token) {
        if (jwtUtil.isValidUserToken(token)) {
            DecodedJWT jwt = jwtUtil.validateUserToken(token);
            String userIdStr = jwt.getClaim(JwtClaimsConstant.USER_ID).asString();
            UUID userId = UUID.fromString(userIdStr);

            CoreUser user = userMapper.selectById(userId);
            if (user != null) {
                return generateToken(user);
            }
        }
        return null;
    }

    /**
     * 获取当前用户信息
     *
     * @param token JWT Token
     * @return 当前用户信息，如果Token无效则返回null
     */
    @Override
    public UserVO getCurrentUser(String token) {
        if (jwtUtil.isValidUserToken(token)) {
            DecodedJWT jwt = jwtUtil.validateUserToken(token);
            String userIdStr = jwt.getClaim(JwtClaimsConstant.USER_ID).asString();
            UUID userId = UUID.fromString(userIdStr);

            CoreUser user = userMapper.selectById(userId);
            if (user != null) {
                return convertToVO(user);
            }
        }
        return null;
    }

    /**
     * 生成用户Token
     *
     * @param user 用户信息
     * @return JWT Token字符串
     */
    private String generateToken(CoreUser user) {
        Map<String, Object> claims = new HashMap<>();
        claims.put(JwtClaimsConstant.USER_ID, user.getUserId().toString());
        claims.put(JwtClaimsConstant.NAME, user.getName());

        return jwtUtil.generateUserToken(claims);
    }

    /**
     * 转换为用户视图对象
     *
     * @param user 用户实体
     * @return 用户视图对象
     */
    private UserVO convertToVO(CoreUser user) {
        UserVO vo = new UserVO();
        BeanUtils.copyProperties(user, vo);
        if (user.getUserId() != null) {
            vo.setUserId(user.getUserId().toString());
        }
        return vo;
    }
}
