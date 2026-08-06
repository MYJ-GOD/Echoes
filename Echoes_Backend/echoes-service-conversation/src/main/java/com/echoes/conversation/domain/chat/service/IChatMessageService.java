package com.echoes.conversation.domain.chat.service;

import com.echoes.conversation.domain.chat.entity.dto.ChatRequestDTO;
import com.echoes.conversation.domain.chat.entity.po.ChatMessage;
import com.echoes.conversation.domain.chat.entity.vo.ChatResponseVO;
import reactor.core.publisher.Flux;

import java.util.List;
import java.util.UUID;

public interface IChatMessageService {

    ChatResponseVO chat(ChatRequestDTO request);

    Flux<String> chatStream(ChatRequestDTO request);

    List<ChatMessage> listMessagesBySessionId(UUID sessionId, Integer limit);

    ChatMessage getChatMessageById(UUID id);

    Boolean feedbackMessage(UUID messageId, Integer feedback);

    /**
     * 保存 Assistant 消息 (用于流式对话结束后的落库)
     */
    ChatMessage saveAssistantMessage(UUID sessionId, String content, UUID parentMessageId);
    /**
     * Update the saved ChatMessage's audio_url field (Mongo) so frontend can retrieve audio.
     *
     * @param messageId UUID of the saved ChatMessage
     * @param audioUrl  retrievable audio endpoint or signed URL
     */
    void updateMessageAudioUrl(UUID messageId, String audioUrl);
}

