package com.echoes.utils;

import java.util.UUID;

/**
 * Common UUID utilities for all services.
 */
public final class UuidUtils {
    private UuidUtils() {}

    public static UUID parseLenient(String s) {
        if (s == null || s.isBlank()) return null;
        String hex = s.replace("-", "");
        if (hex.length() == 32 && hex.matches("[0-9a-fA-F]{32}")) {
            String dashed = hex.replaceFirst(
                "(\\p{XDigit}{8})(\\p{XDigit}{4})(\\p{XDigit}{4})(\\p{XDigit}{4})(\\p{XDigit}+)",
                "$1-$2-$3-$4-$5"
            );
            return UUID.fromString(dashed.toLowerCase());
        }
        return UUID.fromString(s);
    }

    public static String toString(UUID u) {
        return u == null ? null : u.toString();
    }
}


