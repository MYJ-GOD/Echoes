package com.echoes.user.domain.user.repository;

import com.echoes.user.domain.user.entity.po.UserAuth;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.UUID;

/**
 * 用户鉴权Mapper接口
 * 
 * @author echoes
 */
@Mapper
public interface UserAuthMapper {
    
    /**
     * 根据提供方和标识查询鉴权信息
     */
    UserAuth selectByProviderAndOpenId(@Param("provider") String provider, @Param("openId") String openId);
    
    /**
     * 根据用户ID查询鉴权信息
     */
    UserAuth selectByUserId(@Param("userId") UUID userId);
    
    /**
     * 插入鉴权信息
     */
    int insert(UserAuth auth);
    
    /**
     * 软删除鉴权信息（虽然鉴权表没有deleted_at，但可能需要清理）
     * 目前暂未在 UserAuth PO 中定义 deletedAt，此处仅占位，实际逻辑可能需在 UserAuth PO 增加 deletedAt
     * 或者物理删除？Schema v3 中 user_auth 没有 deleted_at，但 core_user 有。
     * 根据 Schema v3，user_auth 确实没有 deleted_at，所以删除用户时通常是物理删除 user_auth 记录
     * 或者保留 user_auth 记录但因 user_id 关联的 core_user 已软删而失效。
     * 
     * 这里暂时不提供删除方法，以 Insert 和 Select 为主。
     */
}
