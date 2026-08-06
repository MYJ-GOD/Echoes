package com.echoes.conversation.domain.chat.repository;

import com.echoes.conversation.domain.chat.entity.po.ConversationTurn;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

/**
 * Conversation Turn Repository
 */
@Repository
public interface ConversationTurnRepository extends JpaRepository<ConversationTurn, UUID> {
    
    /**
     * 根据 turnId 查询
     */
    ConversationTurn findByTurnId(String turnId);
    
    /**
     * 根据 conversationId 和 turnId 查询
     */
    ConversationTurn findByConversationIdAndTurnId(java.util.UUID conversationId, String turnId);

    ConversationTurn findByConversationIdAndIdempotencyKey(java.util.UUID conversationId, String idempotencyKey);
    
    /**
     * 检查是否存在
     */
    boolean existsByTurnId(String turnId);
}
