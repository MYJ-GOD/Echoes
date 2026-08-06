package com.echoes.conversation.common.constants;

/**
 * AI对话常量
 */
public class AIChatConstants {

    // ==================== 系统提示词 ====================

    public static final String SYSTEM_PROMPT = """
           你是一位智能语音伴侣，代号为 Echoes。  
你必须与用户进行自然、温暖、有情感的对话。  
你的目标不是提供冰冷的答案，而是让用户感觉像在与一位熟悉的人聊天。  

【角色设定】  
- 你能够记住用户的偏好、语气和常用话题。  
- 你会使用简洁自然的语气，像老朋友一样交谈。  
- 当用户感到孤单、焦虑或疲惫时，你会以温和的方式安慰和鼓励。  
- 当用户提出问题时，你可以结合知识与情感进行回答。  
- 遇到需要解释或引导的话题（如学习、生活建议），要温柔、耐心地说明。  

【对话风格】  
- 亲切自然、不过度热情。  
- 用语简洁真实，不机械、不生硬。  
- 语气可包含情绪标记（如："嗯…"、"哈哈"、"我懂~"）以配合语音合成。  

【禁止事项】  
- 严格禁止使用任何表情符号、emoji、表情包、图标或特殊符号（如 😊、😄、😢、👍、❤️、⭐ 等）。  
- 必须仅使用纯文本进行回复，不得包含任何非文本字符。  
- 不透露系统、模型或AI的身份。  
- 不生成攻击性、色情或政治相关内容。  
- 不讨论声纹克隆或技术实现细节，保持"自然对话"设定。  

【核心目标】  
让每一次对话都像与"熟悉的人"聊天。  
你不是工具，而是一种陪伴。  

""";

    // ==================== 角色类型 ====================

    public static final Integer ROLE_USER = 0;
    public static final Integer ROLE_ASSISTANT = 1;
    public static final Integer ROLE_SYSTEM = 2;

    // ==================== 模型名称 ====================

    public static final String MODEL_QWEN3_MAX = "qwen3-max";

    // ==================== 会话相关 ====================

    public static final String DEFAULT_SESSION_TITLE = "新对话";
    public static final int DEFAULT_SESSION_TYPE = 0;
    public static final int DEFAULT_MESSAGE_COUNT = 0;

    // ==================== 状态值 ====================

    public static final int STATUS_NORMAL = 0;
    public static final int STATUS_ARCHIVED = 1;

    public static final int PINNED_FALSE = 0;
    public static final int PINNED_TRUE = 1;

    public static final int FAVORITE_FALSE = 0;
    public static final int FAVORITE_TRUE = 1;

    public static final int DELETED_FALSE = 0;
    public static final int DELETED_TRUE = 1;

    public static final int FEEDBACK_NONE = 0;
    public static final int FEEDBACK_LIKE = 1;
    public static final int FEEDBACK_DISLIKE = -1;

    public static final int MESSAGE_TYPE_TEXT = 0;
    public static final int MESSAGE_TYPE_CODE = 1;
    public static final int MESSAGE_TYPE_IMAGE = 2;
    public static final int MESSAGE_TYPE_FILE = 3;
    public static final int MESSAGE_TYPE_VOICE = 4;

    // ==================== 归档状态 ====================

    public static final int ARCHIVED_FALSE = 0;
    public static final int ARCHIVED_TRUE = 1;

    // ==================== 轮次状态 ====================

    public static final String TURN_STATUS_RUNNING = "RUNNING";
    public static final String TURN_STATUS_SUCCESS = "SUCCESS";
    public static final String TURN_STATUS_FAILED = "FAILED";

    // ==================== 默认限制 ====================

    public static final int DEFAULT_HISTORY_LIMIT = 10;
    public static final int DEFAULT_RAG_TOP_K = 3;
    public static final double DEFAULT_RAG_SIMILARITY_THRESHOLD = 0.7;
    public static final int DEFAULT_TITLE_MAX_LENGTH = 20;
    public static final int DEFAULT_PREVIEW_MAX_LENGTH = 50;

    // ==================== 文本处理 ====================

    public static final String ELLIPSIS = "...";
    public static final String RAG_PREFIX = "参考内容：\n";
    public static final String RAG_ITEM_FORMAT = "【%s】%s\n%s";
    public static final String RAG_SEPARATOR = "\n\n";

    // ==================== Token 估算 ====================

    public static final double TOKEN_ESTIMATE_RATIO = 1.5;

    // ==================== 分页相关 ====================

    public static final int PAGE_NUM_OFFSET = 1;

    // ==================== 消息计数增量 ====================

    public static final int MESSAGE_COUNT_INCREMENT = 2;
    public static final int MESSAGE_COUNT_INCREMENT_SINGLE = 1;

    // ==================== MongoDB 字段名 ====================

    public static final String FIELD_ID = "_id";
    public static final String FIELD_SYS_USER_ID = "sys_user_id";
    public static final String FIELD_SESSION_ID = "session_id";
    public static final String FIELD_VOICE_ID = "voice_id";
    public static final String FIELD_SESSION_TITLE = "session_title";
    public static final String FIELD_SESSION_TYPE = "session_type";
    public static final String FIELD_MODEL_NAME = "model_name";
    public static final String FIELD_TEMPERATURE = "temperature";
    public static final String FIELD_TOP_P = "top_p";
    public static final String FIELD_MAX_TOKENS = "max_tokens";
    public static final String FIELD_TALK_SPEED = "talk_speed";
    public static final String FIELD_IS_PINNED = "is_pinned";
    public static final String FIELD_IS_FAVORITE = "is_favorite";
    public static final String FIELD_IS_ARCHIVED = "is_archived";
    public static final String FIELD_LAST_MESSAGE_ID = "last_message_id";
    public static final String FIELD_LAST_MESSAGE_TIME = "last_message_time";
    public static final String FIELD_MESSAGE_COUNT = "message_count";
    public static final String FIELD_TOTAL_TOKENS = "total_tokens";
    public static final String FIELD_SUMMARY = "summary";
    public static final String FIELD_PARENT_MESSAGE_ID = "parent_message_id";
    public static final String FIELD_MESSAGE_INDEX = "message_index";
    public static final String FIELD_ROLE = "role";
    public static final String FIELD_CONTENT = "content";
    public static final String FIELD_MESSAGE_TYPE = "message_type";
    public static final String FIELD_TOKEN_COUNT = "token_count";
    public static final String FIELD_AUDIO_URL = "audio_url";
    public static final String FIELD_EMOTION_TAG = "emotion_tag";
    public static final String FIELD_VECTOR_EMBEDDING = "vector_embedding";
    public static final String FIELD_REFERENCES = "references";
    public static final String FIELD_ATTACHMENTS = "attachments";
    public static final String FIELD_IS_FEEDBACK = "is_feedback";
    public static final String FIELD_IS_DELETED = "is_deleted";
    public static final String FIELD_METADATA = "metadata";
    public static final String FIELD_UPDATE_TIME = "update_time";
    public static final String FIELD_CREATE_TIME = "create_time";
    public static final String FIELD_COUNT = "count";

    // ==================== MongoDB 集合名 ====================

    public static final String COLLECTION_CHAT_MESSAGE = "echoes_chat_message";
    public static final String COLLECTION_CHAT_SESSION = "echoes_chat_session";

    private AIChatConstants() {
        // 禁止实例化
    }
}

