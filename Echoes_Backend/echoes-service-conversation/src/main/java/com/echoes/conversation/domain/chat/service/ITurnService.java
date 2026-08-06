package com.echoes.conversation.domain.chat.service;

import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;

import java.util.List;
import java.util.UUID;

public interface ITurnService {

    ConversationTurn startTurn(UUID conversationId, String turnId, UUID userId, String idempotencyKey, byte[] payloadHash);

    void completeTurn(String turnId, String finalMessageId);

    void failTurn(String turnId, String errorMessage, String errorStage, boolean retryable);

    void failTurn(String turnId, String errorCode, String errorMessage, String errorStage, boolean retryable);

    boolean exists(String turnId);

    long nextSeq(UUID conversationId, String turnId);

    void appendEvent(UUID conversationId, String turnId, long seq, String eventJson);

    List<String> fetchEvents(UUID conversationId, String turnId);
}
