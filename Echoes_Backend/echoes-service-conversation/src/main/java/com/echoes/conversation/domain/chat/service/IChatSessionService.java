package com.echoes.conversation.domain.chat.service;

import com.echoes.conversation.domain.chat.entity.dto.ChatSessionQueryDTO;
import com.echoes.conversation.domain.chat.entity.vo.ChatSessionVO;

import java.util.List;
import java.util.UUID;

public interface IChatSessionService {

    List<ChatSessionVO> listChatSession(ChatSessionQueryDTO chatSessionQueryDTO);

    List<ChatSessionVO> listAllChatSessionByUserId(java.util.UUID sysUserId);

    ChatSessionVO getChatSessionById(UUID id);

    ChatSessionVO addChatSession(UUID courseId, Integer sessionType, String title, java.util.UUID sysUserId);

    Boolean updateChatSessionTitle(UUID id, String title);

    Boolean removeChatSessionById(UUID id);

    Integer removeChatSessionByIds(List<UUID> ids);

    Boolean pinSession(UUID id, Boolean isPinned);

    Boolean favoriteSession(UUID id, Boolean isFavorite);

    Boolean archiveSession(UUID id);

    Boolean updateSessionLastMessage(UUID sessionId, String lastMessage);
}

