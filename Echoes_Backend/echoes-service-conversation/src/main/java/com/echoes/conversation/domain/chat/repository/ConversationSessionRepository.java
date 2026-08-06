package com.echoes.conversation.domain.chat.repository;

import com.echoes.conversation.domain.chat.entity.po.ConversationSession;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * MySQL 会话表 conversation_session 的 Repository
 */
@Repository
public interface ConversationSessionRepository extends JpaRepository<ConversationSession, java.util.UUID> {

    /**
     * 根据用户ID查询会话列表，按开始时间倒序
     */
    List<ConversationSession> findByUserIdAndIsDeletedOrderByLastMessageTimeDesc(java.util.UUID userId, Integer isDeleted);

    /**
     * 根据用户ID分页查询会话列表
     */
    Page<ConversationSession> findByUserIdAndIsDeleted(java.util.UUID userId, Integer isDeleted, Pageable pageable);

    /**
     * 根据用户ID和会话标题查找会话（用于重命名/删除时保持 MySQL 和 Mongo 一致）
     */
    Optional<ConversationSession> findFirstByUserIdAndSessionTitleAndIsDeletedOrderByLastMessageTimeDesc(java.util.UUID userId, String sessionTitle, Integer isDeleted);
}


