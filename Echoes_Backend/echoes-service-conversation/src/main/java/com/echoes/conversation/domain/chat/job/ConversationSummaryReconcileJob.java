package com.echoes.conversation.domain.chat.job;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class ConversationSummaryReconcileJob {

    private final JdbcTemplate jdbcTemplate;

    /**
     * Daily reconcile for conversation_summary aggregate fields.
     * - Fill missing rows from successful turns
     * - Recompute avg latency + last turn time
     */
    @Scheduled(cron = "${conversation.summary.reconcile-cron:0 10 3 * * *}")
    public void reconcile() {
        long start = System.currentTimeMillis();
        try {
            int inserted = jdbcTemplate.update(
                    "INSERT INTO conversation_summary " +
                            "(conversation_id, total_input_tokens, total_output_tokens, avg_latency_ms, last_turn_time, update_time) " +
                            "SELECT t.conversation_id, 0, 0, " +
                            "CAST(AVG(TIMESTAMPDIFF(MICROSECOND, t.start_time, t.end_time) / 1000) AS SIGNED), " +
                            "MAX(t.end_time), NOW() " +
                            "FROM conversation_turn t " +
                            "LEFT JOIN conversation_summary cs ON cs.conversation_id = t.conversation_id " +
                            "WHERE cs.conversation_id IS NULL " +
                            "AND t.status = 'SUCCESS' " +
                            "AND t.start_time IS NOT NULL AND t.end_time IS NOT NULL " +
                            "GROUP BY t.conversation_id");

            int updated = jdbcTemplate.update(
                    "UPDATE conversation_summary cs " +
                            "JOIN ( " +
                            "  SELECT t.conversation_id AS cid, " +
                            "         CAST(AVG(TIMESTAMPDIFF(MICROSECOND, t.start_time, t.end_time) / 1000) AS SIGNED) AS avg_ms, " +
                            "         MAX(t.end_time) AS last_end " +
                            "  FROM conversation_turn t " +
                            "  WHERE t.status = 'SUCCESS' " +
                            "    AND t.start_time IS NOT NULL AND t.end_time IS NOT NULL " +
                            "  GROUP BY t.conversation_id " +
                            ") a ON a.cid = cs.conversation_id " +
                            "SET cs.avg_latency_ms = a.avg_ms, " +
                            "    cs.last_turn_time = a.last_end, " +
                            "    cs.update_time = NOW()");

            log.info("conversation_summary reconcile finished: inserted={}, updated={}, costMs={}",
                    inserted, updated, System.currentTimeMillis() - start);
        } catch (Exception e) {
            log.error("conversation_summary reconcile failed", e);
        }
    }
}
