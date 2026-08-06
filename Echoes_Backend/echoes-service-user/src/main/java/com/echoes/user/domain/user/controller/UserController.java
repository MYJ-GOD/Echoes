package com.echoes.user.domain.user.controller;

import com.echoes.user.common.result.Result;
import com.echoes.user.domain.user.entity.dto.UpdateUserDTO;
import com.echoes.user.domain.user.entity.vo.UserVO;
import com.echoes.user.domain.user.service.IUserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import com.echoes.utils.UuidUtils;

/**
 * 用户控制器
 * 提供用户资料查询与更新接口
 */
@RestController
@RequestMapping("/user")
@RequiredArgsConstructor
@Tag(name = "用户管理", description = "用户资料查询与更新接口")
public class UserController {

    private final IUserService userService;

    /**
     * 根据ID获取用户信息
     *
     * @param id 用户ID
     * @return 用户详细信息
     */
    @GetMapping("/{id}")
    @Operation(summary = "根据ID获取用户信息", description = "根据用户ID查询用户详细信息")
    public Result<UserVO> getUserById(@PathVariable("id") String id) {
        java.util.UUID uid = UuidUtils.parseLenient(id);
        UserVO userVO = userService.getUserById(uid);
        return Result.success(userVO);
    }

    /**
     * 更新用户信息
     *
     * @param id        用户ID
     * @param updateDTO 更新参数
     * @return 更新后的用户信息
     */
    @PutMapping("/{id}")
    @Operation(summary = "更新用户信息", description = "更新用户的账号、邮箱、电话号")
    public Result<UserVO> updateUser(
            @PathVariable("id") String id,
            @Valid @RequestBody UpdateUserDTO updateDTO) {
        java.util.UUID uid = UuidUtils.parseLenient(id);
        UserVO userVO = userService.updateUser(uid, updateDTO);
        return Result.success(userVO);
    }
}