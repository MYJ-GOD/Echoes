package com.echoes.admin.domain.governance.repository;

import com.echoes.admin.domain.governance.entity.po.AdminConversationTurn;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.UUID;

/**
 * 对话 Turn 记录 Mapper（扩展查询）
 */
@Mapper
public interface AdminConversationTurnMapper {

    /**
     * 根据 TurnId 查询
     */
    AdminConversationTurn selectByTurnId(@Param("turnId") String turnId);

    /**
     * 按会话 ID 查询 Turn 列表
     */
    List<AdminConversationTurn> selectTurnsBySessionId(
            @Param("conversationId") UUID conversationId,
            @Param("limit") Integer limit
    );

    /**
     * 查询失败 Turn 统计（按 error_code 分组）
     */
    List<FailureStatistics> selectFailureStatistics(
            @Param("timeFrom") java.time.LocalDateTime timeFrom,
            @Param("timeTo") java.time.LocalDateTime timeTo
    );

    /**
     * 查询失败 Turn 详情
     */
    List<AdminConversationTurn> selectFailedTurns(
            @Param("errorCode") String errorCode,
            @Param("errorStage") String errorStage,
            @Param("offset") Integer offset,
            @Param("limit") Integer limit
    );

    /**
     * 统计失败 Turn 总数
     */
    int countFailedTurns(
            @Param("errorCode") String errorCode,
            @Param("errorStage") String errorStage
    );

    /**
     * 统计 Turn 总数
     */
    int countTotalTurns();

    /**
     * 失败统计 VO
     */
    class FailureStatistics {
        private String errorCode;
        private String errorStage;
        private int count;

        public String getErrorCode() { return errorCode; }
        public void setErrorCode(String errorCode) { this.errorCode = errorCode; }
        public String getErrorStage() { return errorStage; }
        public void setErrorStage(String errorStage) { this.errorStage = errorStage; }
        public int getCount() { return count; }
        public void setCount(int count) { this.count = count; }
    }
}
