package com.echoes.rag.domain.knowledge.service;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.echoes.rag.domain.knowledge.entity.KnowledgeBase;
import com.echoes.rag.domain.knowledge.enums.KnowledgeBaseStatus;
import com.echoes.rag.domain.knowledge.enums.KnowledgeBaseVisibility;
import com.echoes.rag.domain.knowledge.repository.KnowledgeBaseMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.sql.ResultSet;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 知识库服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeBaseService extends ServiceImpl<KnowledgeBaseMapper, KnowledgeBase> {

    private final JdbcTemplate jdbcTemplate;

    /**
     * 查询用户的知识库列表
     */
    public List<KnowledgeBase> listByUser(String userId, boolean includeDeleted) {
        if (!StringUtils.hasText(userId)) {
            throw new IllegalArgumentException("User ID cannot be empty");
        }

        StringBuilder sql = new StringBuilder(
                "SELECT kb_id,name,description,owner_user_id,visibility,status,is_deleted " +
                        "FROM knowledge_base WHERE owner_user_id = ? ");
        if (!includeDeleted) {
            sql.append("AND is_deleted = 0 ");
        }
        sql.append("ORDER BY create_time DESC");
        return jdbcTemplate.query(sql.toString(), this::mapKnowledgeBase, userId);
    }

    /**
     * 查询公共知识库
     */
    public List<KnowledgeBase> listPublic() {
        String sql = "SELECT kb_id,name,description,owner_user_id,visibility,status,is_deleted " +
                "FROM knowledge_base WHERE visibility = ? AND status = ? AND is_deleted = 0 " +
                "ORDER BY create_time DESC";
        return jdbcTemplate.query(sql, this::mapKnowledgeBase, KnowledgeBaseVisibility.PUBLIC.getCode(), KnowledgeBaseStatus.ACTIVE.getCode());
    }

    /**
     * 创建知识库
     */
    @Transactional(rollbackFor = Exception.class)
    public KnowledgeBase create(KnowledgeBase knowledgeBase) {
        knowledgeBase.setIsDeleted(0);
        knowledgeBase.setStatus(KnowledgeBaseStatus.ACTIVE.getCode());
        if (knowledgeBase.getVisibility() == null) {
            knowledgeBase.setVisibility(KnowledgeBaseVisibility.PRIVATE.getCode());
        }
        save(knowledgeBase);
        return knowledgeBase;
    }

    /**
     * 更新知识库
     */
    @Transactional(rollbackFor = Exception.class)
    public KnowledgeBase update(String kbId, KnowledgeBase knowledgeBase) {
        knowledgeBase.setKbId(kbId);
        updateById(knowledgeBase);
        return getById(kbId);
    }

    /**
     * 删除知识库（软删除）
     */
    @Transactional(rollbackFor = Exception.class)
    public void delete(String kbId) {
        KnowledgeBase kb = getById(kbId);
        if (kb != null) {
            kb.setIsDeleted(1);
            kb.setDeletedAt(LocalDateTime.now());
            updateById(kb);
        }
    }

    /**
     * 检查用户是否有权限访问知识库
     */
    public boolean hasPermission(String kbId, String userId, String permission) {
        KnowledgeBase kb = getById(kbId);
        if (kb == null || kb.getIsDeleted() == 1) {
            return false;
        }

        // 公共知识库所有人可访问
        if (KnowledgeBaseVisibility.PUBLIC.getCode().equals(kb.getVisibility())) {
            return true;
        }

        // 所有者
        if (userId != null && userId.equals(kb.getOwnerUserId())) {
            return true;
        }

        // SHARED 可见性：需要检查共享关系表（待实现）
        // TODO: 实现 knowledge_base_share 表后，检查用户是否在共享列表中
        if (KnowledgeBaseVisibility.SHARED.getCode().equals(kb.getVisibility()) && userId != null) {
            log.warn("SHARED 权限检查未实现，当前拒绝访问。需要实现 knowledge_base_share 表后再放行：kbId={}, userId={}", kbId, userId);
            return false;
        }

        return false;
    }

    private KnowledgeBase mapKnowledgeBase(ResultSet rs, int rowNum) throws java.sql.SQLException {
        KnowledgeBase kb = new KnowledgeBase();
        kb.setKbId(rs.getString("kb_id"));
        kb.setName(rs.getString("name"));
        kb.setDescription(rs.getString("description"));
        kb.setOwnerUserId(rs.getString("owner_user_id"));
        kb.setVisibility(rs.getString("visibility"));
        kb.setStatus(rs.getString("status"));
        kb.setIsDeleted(rs.getObject("is_deleted") != null ? rs.getInt("is_deleted") : null);
        return kb;
    }
}
