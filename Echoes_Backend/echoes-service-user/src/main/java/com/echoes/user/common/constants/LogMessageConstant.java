package com.echoes.user.common.constants;

/**
 * 日志消息常量类
 * 统一管理系统中使用的日志消息模板
 */
public class LogMessageConstant {
    
    // ========== 异常处理相关常量 ==========
    /**
     * 业务异常日志模板
     */
    public static final String BUSINESS_EXCEPTION = "业务异常: {}";
    
    /**
     * 基础异常日志模板
     */
    public static final String BASE_EXCEPTION = "基础异常: {}";
    
    /**
     * 登录失败日志模板
     */
    public static final String LOGIN_FAILED = "登录失败: {}";
    
    /**
     * 账号不存在日志模板
     */
    public static final String ACCOUNT_NOT_FOUND = "账号不存在: {}";
    
    /**
     * 密码错误日志模板
     */
    public static final String PASSWORD_ERROR = "密码错误: {}";
    
    /**
     * 账号被锁定日志模板
     */
    public static final String ACCOUNT_LOCKED = "账号被锁定: {}";
    
    /**
     * 用户未登录日志模板
     */
    public static final String USER_NOT_LOGIN = "用户未登录: {}";
    
    /**
     * 删除不允许日志模板
     */
    public static final String DELETION_NOT_ALLOWED = "删除不允许: {}";
    
    /**
     * 参数验证失败日志模板
     */
    public static final String PARAM_VALIDATION_FAILED = "参数验证失败: {}";
    
    /**
     * 参数绑定失败日志模板
     */
    public static final String PARAM_BIND_FAILED = "参数绑定失败: {}";
    
    /**
     * 约束验证失败日志模板
     */
    public static final String CONSTRAINT_VIOLATION_FAILED = "约束验证失败: {}";
    
    /**
     * 缺少请求参数日志模板
     */
    public static final String MISSING_REQUEST_PARAM = "缺少请求参数: {}";
    
    /**
     * HTTP消息不可读日志模板
     */
    public static final String HTTP_MESSAGE_NOT_READABLE = "HTTP消息不可读: {}";
    
    /**
     * 请求方法不支持日志模板
     */
    public static final String METHOD_NOT_SUPPORTED = "请求方法不支持: {}";
    
    /**
     * 请求路径不存在日志模板
     */
    public static final String PATH_NOT_FOUND = "请求路径不存在: {}";
    
    /**
     * 文件上传大小超限日志模板
     */
    public static final String FILE_SIZE_EXCEEDED = "文件上传大小超限: {}";
    
    /**
     * 文件上传异常日志模板
     */
    public static final String FILE_UPLOAD_EXCEPTION = "文件上传异常: {}";
    
    /**
     * 数据重复日志模板
     */
    public static final String DATA_DUPLICATE = "数据重复: {}";
    
    /**
     * SQL完整性约束违反日志模板
     */
    public static final String SQL_CONSTRAINT_VIOLATION = "SQL完整性约束违反: {}";
    
    /**
     * 参数异常日志模板
     */
    public static final String ILLEGAL_ARGUMENT = "参数异常: {}";
    
    /**
     * 运行时异常日志模板
     */
    public static final String RUNTIME_EXCEPTION = "运行时异常: {}";
    
    /**
     * 客户端断开连接日志模板
     */
    public static final String CLIENT_ABORT = "客户端断开连接: {}";
    
    /**
     * 客户端断开 SSE 连接日志模板
     */
    public static final String CLIENT_ABORT_SSE = "客户端断开 SSE 连接: {}";
    
    /**
     * SSE 流式响应异常日志模板
     */
    public static final String SSE_STREAM_EXCEPTION = "SSE 流式响应异常: {}";
    
    /**
     * SSE 流式响应异常（响应已提交）日志模板
     */
    public static final String SSE_STREAM_EXCEPTION_COMMITTED = "SSE 流式响应异常（响应已提交）: {}";
    
    /**
     * 写入 SSE 错误响应失败日志模板
     */
    public static final String SSE_WRITE_ERROR_FAILED = "写入 SSE 错误响应失败（连接可能已断开）: {}";
    
    /**
     * 未知异常日志模板
     */
    public static final String UNKNOWN_EXCEPTION = "未知异常: {}";
    
    // ========== 业务操作相关常量 ==========
    /**
     * 用户登录成功日志模板
     */
    public static final String USER_LOGIN_SUCCESS = "用户登录成功: userId={}, name={}";
    
    /**
     * 用户注册成功日志模板
     */
    public static final String USER_REGISTER_SUCCESS = "用户注册成功: userId={}, name={}";
    
    /**
     * 用户登出成功日志模板
     */
    public static final String USER_LOGOUT_SUCCESS = "用户登出成功: userId={}, token已加入黑名单";
    
    /**
     * Token刷新成功日志模板
     */
    public static final String TOKEN_REFRESH_SUCCESS = "Token刷新成功: userId={}";
    
    /**
     * 登录失败：用户不存在日志模板
     */
    public static final String LOGIN_FAILED_USER_NOT_FOUND = "登录失败: 用户不存在, account={}";
    
    /**
     * 登录失败：密码错误日志模板
     */
    public static final String LOGIN_FAILED_PASSWORD_ERROR = "登录失败: 密码错误, userId={}";
    
    /**
     * 登录失败：账户状态异常日志模板
     */
    public static final String LOGIN_FAILED_STATUS_ERROR = "登录失败: 账户状态异常, userId={}, status={}";
    
    /**
     * 注册失败：用户名已存在日志模板
     */
    public static final String REGISTER_FAILED_NAME_EXISTS = "注册失败: 用户名已存在, name={}";
    
    /**
     * 注册失败：手机号已存在日志模板
     */
    public static final String REGISTER_FAILED_PHONE_EXISTS = "注册失败: 手机号已存在, phoneNumber={}";
    
    /**
     * 注册失败：邮箱已存在日志模板
     */
    public static final String REGISTER_FAILED_EMAIL_EXISTS = "注册失败: 邮箱已存在, email={}";
    
    /**
     * 登出失败：token解析错误日志模板
     */
    public static final String LOGOUT_FAILED_TOKEN_PARSE_ERROR = "登出失败: token解析错误";
    
    /**
     * Token验证失败：Token在黑名单中日志模板
     */
    public static final String TOKEN_VALIDATE_FAILED_BLACKLIST = "Token验证失败: Token在黑名单中";
    
    /**
     * Token验证失败日志模板
     */
    public static final String TOKEN_VALIDATE_FAILED = "Token验证失败: {}";
    
    /**
     * Token刷新失败日志模板
     */
    public static final String TOKEN_REFRESH_FAILED = "Token刷新失败";
    
    /**
     * 获取当前用户信息失败日志模板
     */
    public static final String GET_CURRENT_USER_FAILED = "获取当前用户信息失败";
    
    /**
     * 用户不存在日志模板
     */
    public static final String USER_NOT_FOUND = "用户不存在: userId={}";
    
    // ========== 系统操作相关常量 ==========
    /**
     * 白名单路径，直接放行日志模板
     */
    public static final String WHITELIST_PATH_ALLOWED = "白名单路径，直接放行: {}";
    
    /**
     * 请求缺少Token日志模板
     */
    public static final String REQUEST_MISSING_TOKEN = "请求缺少Token: path={}";
    
    /**
     * Token验证成功日志模板
     */
    public static final String TOKEN_VALIDATE_SUCCESS = "Token验证成功，添加用户信息到请求头: userId={}, username={}";
    
    /**
     * 解析Token失败日志模板
     */
    public static final String TOKEN_PARSE_FAILED = "解析Token失败";
    
    /**
     * Token验证失败日志模板
     */
    public static final String TOKEN_VERIFY_FAILED = "Token验证失败: path={}";
    
    /**
     * Token验证异常日志模板
     */
    public static final String TOKEN_VERIFY_EXCEPTION = "Token验证异常: path={}";
    
    /**
     * 序列化错误响应失败日志模板
     */
    public static final String SERIALIZE_ERROR_RESPONSE_FAILED = "序列化错误响应失败";
    
    // ========== 错误消息常量 ==========
    /**
     * 参数验证失败默认消息
     */
    public static final String PARAM_VALIDATION_FAILED_MSG = "参数验证失败";
    
    /**
     * 参数绑定失败默认消息
     */
    public static final String PARAM_BIND_FAILED_MSG = "参数绑定失败";
    
    /**
     * 数据已存在，请勿重复添加
     */
    public static final String DATA_ALREADY_EXISTS_MSG = "数据已存在，请勿重复添加";
    
    /**
     * 数据操作失败，请检查数据完整性
     */
    public static final String DATA_OPERATION_FAILED_MSG = "数据操作失败，请检查数据完整性";
    
    /**
     * 必填字段不能为空
     */
    public static final String REQUIRED_FIELD_EMPTY_MSG = "必填字段不能为空";
    
    /**
     * 存在关联数据，操作失败
     */
    public static final String RELATED_DATA_EXISTS_MSG = "存在关联数据，操作失败";
    
    /**
     * 缺少必要的请求参数
     */
    public static final String MISSING_REQUIRED_PARAM_MSG = "缺少必要的请求参数: {}";
    
    /**
     * 请求体格式错误，请检查JSON格式
     */
    public static final String REQUEST_BODY_FORMAT_ERROR_MSG = "请求体格式错误，请检查JSON格式";
    
    /**
     * 不支持的请求方法
     */
    public static final String UNSUPPORTED_METHOD_MSG = "不支持的请求方法: {}";
    
    /**
     * 请求路径不存在
     */
    public static final String PATH_NOT_FOUND_MSG = "请求路径不存在: {}";
    
    /**
     * 上传的文件大小超过限制，请选择较小的文件
     */
    public static final String FILE_SIZE_EXCEEDED_MSG = "上传的文件大小超过限制，请选择较小的文件";
    
    /**
     * 文件上传失败，请重试
     */
    public static final String FILE_UPLOAD_FAILED_MSG = "文件上传失败，请重试";
    
    /**
     * 服务暂时不可用，请稍后重试
     */
    public static final String SERVICE_UNAVAILABLE_MSG = "服务暂时不可用，请稍后重试";
    
    /**
     * 系统发生未知错误，请联系管理员
     */
    public static final String SYSTEM_UNKNOWN_ERROR_MSG = "系统发生未知错误，请联系管理员";
    
    /**
     * 请求体格式错误，请检查JSON格式
     */
    public static final String JSON_FORMAT_ERROR_MSG = "请求体格式错误，请检查JSON格式";
    
    /**
     * SSE 错误消息格式
     */
    public static final String SSE_ERROR_FORMAT = "data: {\"type\":\"error\",\"data\":\"%s\"}\n\n";
    
    /**
     * SSE 错误消息
     */
    public static final String SSE_ERROR_MESSAGE = "系统发生未知错误，请联系管理员";
    
    /**
     * SSE 路径标识
     */
    public static final String SSE_PATH_STREAM = "/stream";
    
    /**
     * SSE 路径标识
     */
    public static final String SSE_PATH_CHAT = "/chat";
    
    /**
     * Bearer Token 前缀
     */
    public static final String BEARER_PREFIX = "Bearer ";
    
    /**
     * Bearer Token 前缀长度
     */
    public static final int BEARER_PREFIX_LENGTH = 7;
    
    /**
     * Token 黑名单前缀
     */
    public static final String TOKEN_BLACKLIST_PREFIX = "jwt:blacklist:";
    
    /**
     * 无效Token值
     */
    public static final String INVALID_TOKEN_VALUE = "invalid";
    
    /**
     * 黑名单过期时间（小时）
     */
    public static final long BLACKLIST_TTL_HOURS = 1;
    
    /**
     * 字符串常量：Duplicate entry
     */
    public static final String DUPLICATE_ENTRY = "Duplicate entry";
    
    /**
     * 字符串常量：cannot be null
     */
    public static final String CANNOT_BE_NULL = "cannot be null";
    
    /**
     * 字符串常量：foreign key constraint
     */
    public static final String FOREIGN_KEY_CONSTRAINT = "foreign key constraint";
    
    /**
     * 字符串常量：账号
     */
    public static final String ACCOUNT = "账号";
    
    private LogMessageConstant() {
        // 工具类不允许实例化
    }
}
