package com.echoes.voice.domain.voice.enums;

import lombok.Getter;

/**
 * Voice asset status.
 */
@Getter
public enum AssetStatus {
    CREATING("creating", "Creating"),
    READY("ready", "Ready"),
    FAILED("failed", "Failed"),
    DELETED("deleted", "Deleted");

    private final String code;
    private final String desc;

    AssetStatus(String code, String desc) {
        this.code = code;
        this.desc = desc;
    }

    /**
     * Find enum by code (also supports enum name).
     */
    public static AssetStatus fromCode(String code) {
        if (code == null || code.isBlank()) {
            return null;
        }
        for (AssetStatus status : values()) {
            if (status.code.equalsIgnoreCase(code) || status.name().equalsIgnoreCase(code)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown status code: " + code);
    }
}
