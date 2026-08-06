package com.echoes.voice.domain.voice.entity.po;

import com.echoes.entity.BaseEntity;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Voice audit log record.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class VoiceAuditLog extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    private UUID auditId;

    private UUID voiceAssetId;

    private UUID actorUserId;

    /** CREATE/DELETE/UPDATE/GRANT/REVOKE/USE */
    private String action;

    /** ALLOWED/DENIED/ERROR */
    private String result;

    /** JSON details */
    private String details;

    /** Business event time */
    private LocalDateTime ts;
}
