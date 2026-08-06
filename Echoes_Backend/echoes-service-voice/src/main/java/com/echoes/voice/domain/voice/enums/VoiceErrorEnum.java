package com.echoes.voice.domain.voice.enums;

import com.echoes.enumeration.BaseEnum;
import lombok.AllArgsConstructor;
import lombok.Getter;

/**
 * 语音服务错误码枚举
 * 统一管理语音服务中的错误码和错误消息
 */
@Getter
@AllArgsConstructor
public enum VoiceErrorEnum implements BaseEnum {

    // ========== 参数相关错误 60001-60010 ==========

    /**
     * 音色名称不能为空
     */
    VOICE_NAME_EMPTY(60001, "音色名称不能为空"),

    /**
     * 文本内容不能为空
     */
    TEXT_EMPTY(60002, "文本内容不能为空"),

    /**
     * 参数验证失败
     */
    PARAM_VALIDATION_FAILED(60003, "参数验证失败"),

    // ========== 语音合成相关错误 60011-60030 ==========

    /**
     * 语音合成失败
     */
    SYNTHESIS_FAILED(60011, "语音合成失败"),

    /**
     * 音色文件不存在
     */
    VOICE_FILE_NOT_FOUND(60012, "音色文件不存在"),

    /**
     * 音色文件格式错误
     */
    VOICE_FILE_FORMAT_ERROR(60013, "音色文件格式错误"),

    /**
     * 音频生成失败
     */
    AUDIO_GENERATION_FAILED(60014, "音频生成失败"),

    /**
     * 音频编码失败
     */
    AUDIO_ENCODING_FAILED(60015, "音频编码失败"),

    // ========== 流式处理相关错误 60031-60050 ==========

    /**
     * 流式请求解析失败
     */
    STREAM_PARSE_FAILED(60031, "流式请求解析失败"),

    /**
     * 流式响应生成失败
     */
    STREAM_RESPONSE_FAILED(60032, "流式响应生成失败"),

    /**
     * 流式连接中断
     */
    STREAM_CONNECTION_INTERRUPTED(60033, "流式连接中断"),

    /**
     * 流式超时
     */
    STREAM_TIMEOUT(60034, "流式请求超时"),

    // ========== 服务相关错误 60051-60070 ==========

    /**
     * 语音服务不可用
     */
    SERVICE_UNAVAILABLE(60051, "语音服务不可用"),

    /**
     * CosyVoice 服务连接失败
     */
    COSYVOICE_CONNECTION_FAILED(60052, "CosyVoice 服务连接失败"),

    /**
     * CosyVoice 服务响应错误
     */
    COSYVOICE_RESPONSE_ERROR(60053, "CosyVoice 服务响应错误"),

    /**
     * 服务内部错误
     */
    INTERNAL_ERROR(60054, "服务内部错误"),

    // ========== 缓存相关错误 60071-60080 ==========

    /**
     * 缓存操作失败
     */
    CACHE_OPERATION_FAILED(60071, "缓存操作失败"),

    /**
     * 缓存键生成失败
     */
    CACHE_KEY_GENERATION_FAILED(60072, "缓存键生成失败"),

    // ========== 文件相关错误 60081-60090 ==========

    /**
     * 语音克隆失败
     */
    VOICE_CLONE_FAILED(60081, "语音克隆失败"),

    /**
     * 本地文件不存在
     */
    LOCAL_FILE_NOT_FOUND(60082, "本地文件不存在"),

    /**
     * 数据库操作失败
     */
    DATABASE_OPERATION_FAILED(60083, "数据库操作失败"),

    /**
     * 声纹模型不存在
     */
    VOICE_MODEL_NOT_FOUND(60084, "声纹模型不存在"),

    /**
     * 模型文件下载失败
     */
    VOICE_MODEL_DOWNLOAD_FAILED(60085, "模型文件下载失败"),

    /**
     * 模型文件保存失败
     */
    VOICE_MODEL_SAVE_FAILED(60086, "模型文件保存失败"),

    // ========== 音色资产相关错误 60091-60100 ==========

    /**
     * 音色资产不存在
     */
    VOICE_ASSET_NOT_FOUND(60091, "音色资产不存在"),

    /**
     * 用户音色数量已达上限
     */
    MAX_VOICE_LIMIT_EXCEEDED(60092, "用户音色数量已达上限"),

    /**
     * 无权访问该音色
     */
    PERMISSION_DENIED(60093, "无权访问该音色"),

    /**
     * 用户ID不能为空
     */
    USER_ID_REQUIRED(60094, "用户ID不能为空"),

    /**
     * 参考音频不存在
     */
    VOICE_REF_NOT_FOUND(60095, "参考音频不存在或已过期"),

    /**
     * 训练任务发送失败
     */
    VOICE_TRAINING_FAILED(60096, "训练任务发送失败");

    private final int code;
    private final String message;

    /**
     * 根据错误码获取枚举
     *
     * @param code 错误码
     * @return 对应的枚举，如果不存在则返回 null
     */
    public static VoiceErrorEnum fromCode(int code) {
        for (VoiceErrorEnum error : values()) {
            if (error.getCode() == code) {
                return error;
            }
        }
        return null;
    }

    /**
     * 判断是否为有效的错误码
     *
     * @param code 错误码
     * @return 是否为有效的错误码
     */
    public static boolean isValid(int code) {
        return fromCode(code) != null;
    }
}
