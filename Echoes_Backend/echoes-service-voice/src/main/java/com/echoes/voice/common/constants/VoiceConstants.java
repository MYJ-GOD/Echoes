package com.echoes.voice.common.constants;

/**
 * 语音服务常量类
 * 统一管理语音服务中使用的常量
 */
public class VoiceConstants {

    // ========== 流式相关常量 ==========

    /**
     * SSE 数据前缀
     */
    public static final String SSE_DATA_PREFIX = "data: ";

    /**
     * SSE 行分隔符
     */
    public static final String SSE_LINE_SEPARATOR = "\n\n";

    /**
     * SSE 单行分隔符
     */
    public static final String SSE_SINGLE_LINE_SEPARATOR = "\n";

    /**
     * SSE 结束标记
     */
    public static final String SSE_DONE = "[DONE]";

    /**
     * 默认音色名称
     */
    public static final String DEFAULT_VOICE_NAME = "default";

    /**
     * 流式请求参数名
     */
    public static final String STREAM_PARAM = "stream";

    /**
     * 流式格式参数名
     */
    public static final String STREAM_FORMAT_PARAM = "stream_format";

    /**
     * NDJSON 格式
     */
    public static final String STREAM_FORMAT_NDJSON = "ndjson";

    /**
     * 二进制格式
     */
    public static final String STREAM_FORMAT_BINARY = "binary";

    // ========== 文本处理相关常量 ==========

    /**
     * 句子分隔符正则表达式
     * 支持中文和英文标点：句号、问号、感叹号、分号
     */
    public static final String SENTENCE_PATTERN = "([\\u3002\\uff1f\\uff01.?!;\\uff1b]+)";

    /**
     * 最小句子长度（用于判断是否为完整句子）
     */
    public static final int MIN_SENTENCE_LENGTH = 2;

    // ========== 流式处理相关常量 ==========

    /**
     * 文本流缓冲区大小
     */
    public static final int TEXT_BUFFER_SIZE = 1024;

    /**
     * 音频流并发度（同时处理的句子数）
     */
    public static final int AUDIO_STREAM_CONCURRENCY = 3;

    /**
     * 音频流延迟（毫秒）
     */
    public static final long AUDIO_STREAM_DELAY_MS = 50;

    // ========== 错误消息常量 ==========

    /**
     * 音色名称不能为空
     */
    public static final String ERROR_VOICE_NAME_EMPTY = "音色名称不能为空";

    /**
     * 文本内容不能为空
     */
    public static final String ERROR_TEXT_EMPTY = "文本内容不能为空";

    /**
     * 流式请求解析失败
     */
    public static final String ERROR_STREAM_PARSE_FAILED = "流式请求解析失败";

    /**
     * 语音合成失败
     */
    public static final String ERROR_SYNTHESIS_FAILED = "语音合成失败";

    /**
     * 服务不可用
     */
    public static final String ERROR_SERVICE_UNAVAILABLE = "语音服务不可用";

    /**
     * 流式响应生成失败
     */
    public static final String ERROR_STREAM_RESPONSE_FAILED = "流式响应生成失败";

    // ========== JSON 字段名常量 ==========

    /**
     * 事件类型字段
     */
    public static final String JSON_FIELD_TYPE = "type";

    /**
     * 数据字段
     */
    public static final String JSON_FIELD_DATA = "data";

    /**
     * 音频字段
     */
    public static final String JSON_FIELD_AUDIO = "audio";

    /**
     * 文本字段
     */
    public static final String JSON_FIELD_TEXT = "text";

    /**
     * 采样率字段
     */
    public static final String JSON_FIELD_SAMPLE_RATE = "sample_rate";

    /**
     * 错误字段
     */
    public static final String JSON_FIELD_ERROR = "error";

    /**
     * 成功字段
     */
    public static final String JSON_FIELD_SUCCESS = "success";

    // ========== HTTP 相关常量 ==========

    /**
     * 流式合成接口路径
     */
    public static final String PATH_SYNTHESIZE_STREAM = "/voice/inference/synthesize-stream";

    /**
     * 文本合成接口路径
     */
    public static final String PATH_SYNTHESIZE_TEXT = "/voice/inference/synthesize-text";

    /**
     * 流式超时时间（分钟）
     */
    public static final int STREAM_TIMEOUT_MINUTES = 10;

    /**
     * 连接超时时间（秒）
     */
    public static final int CONNECT_TIMEOUT_SECONDS = 10;

    // ========== OSS 路径相关常量 ==========

    /**
     * 声纹模型文件在 OSS 中的根目录前缀
     * 示例：voice-models/{userId}/yyyy/MM/dd/xxx.pt
     */
    public static final String OSS_VOICE_MODEL_PREFIX = "voice-models";

    /**
     * 原始音频在 OSS 中的根目录前缀
     * 示例：voice-original/{userId}/yyyy/MM/dd/xxx.wav
     */
    public static final String OSS_ORIGINAL_AUDIO_PREFIX = "voice-original";

    /**
     * OSS 中音频文件默认扩展名
     */
    public static final String OSS_AUDIO_EXT_WAV = ".wav";

    /**
     * OSS 中声纹模型文件默认扩展名
     */
    public static final String OSS_MODEL_EXT_PT = ".pt";

    // ========== 模型缓存相关常量 ==========

    /**
     * Redis 缓存键前缀（模型文件路径缓存）
     */
    public static final String CACHE_MODEL_PREFIX = "voice:model:";

    /**
     * 本地模型缓存目录
     */
    public static final String LOCAL_MODEL_CACHE_DIR = "cache/voices";

    /**
     * 模型文件缓存过期时间（小时）
     */
    public static final int MODEL_CACHE_TTL_HOURS = 24;

    /**
     * OSS 签名 URL 有效期（分钟）
     */
    public static final int OSS_PRESIGNED_URL_EXPIRATION_MINUTES = 60;

    private VoiceConstants() {
        // 工具类不允许实例化
    }
}