package com.echoes.voice.domain.voice.entity.po;

import com.echoes.entity.BaseEntity;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.io.Serial;
import java.time.LocalDateTime;

/**
 * 用户与音色资产的绑定关系表
 * 对应表：user_voice_link
 *
 * @author echoes
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class UserVoiceLink extends BaseEntity {

    @Serial
    private static final long serialVersionUID = 1L;

    /**
     * 关系主键 (link_id)
     */
    private java.util.UUID linkId;

    /**
     * 用户 ID (user_id)
     */
    private java.util.UUID userId;

    /**
     * 音色资产 ID (voice_asset_id)
     */
    private java.util.UUID voiceAssetId;

    /**
     * 用户自定义别名 (nickname)
     */
    private String nickname;

    /**
     * 是否默认音色 (is_default)
     */
    private Integer isDefault;

    /**
     * 是否已删除 (is_deleted)
     */
    private Integer isDeleted;

    /**
     * 删除时间 (deleted_at)
     */
    private java.time.LocalDateTime deletedAt;

    /**
     * 创建时间 (create_time)
     */
    private LocalDateTime createTime;

    /**
     * 更新时间 (update_time)
     */
    private LocalDateTime updateTime;
}
