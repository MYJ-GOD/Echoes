package com.echoes.conversation.domain.chat.controller;

import com.echoes.conversation.domain.chat.client.VoiceServiceWebClient;
import com.echoes.conversation.config.JwtProperties;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpServletRequest;

@RestController
@RequestMapping("/conversation/audio")
@RequiredArgsConstructor
@Slf4j
public class ConversationAudioController {

    private final VoiceServiceWebClient voiceServiceWebClient;
    private final org.springframework.jdbc.core.JdbcTemplate jdbcTemplate;
    private final JwtProperties jwtProperties;

    @GetMapping("/{refId}")
    public ResponseEntity<?> getAudioUrl(@PathVariable("refId") String refId,
                                         @RequestHeader(value = "Authorization", required = false) String authorizationHeader) {
        try {
            // 1) Query audio_asset for storage_key and owner
            String sql = "SELECT storage_key, HEX(owner_user_id) as owner_hex, conversation_id FROM audio_asset WHERE audio_ref = ? AND is_deleted = 0 LIMIT 1";
            java.util.Map<String, Object> row = null;
            try {
                row = jdbcTemplate.queryForMap(sql, refId);
            } catch (org.springframework.dao.EmptyResultDataAccessException ex) {
                row = null;
            }

            if (row == null) {
                // fallback: ask voice service for ref info
                JsonNode node = voiceServiceWebClient.getVoiceReference(refId, null, null, null).block();
                if (node == null) return ResponseEntity.notFound().build();
                if (node.has("signed_url")) {
                    return ResponseEntity.ok().body(java.util.Map.of("url", node.get("signed_url").asText()));
                } else if (node.has("url")) {
                    return ResponseEntity.ok().body(java.util.Map.of("url", node.get("url").asText()));
                } else if (node.has("storage_key")) {
                    String storageKey = node.get("storage_key").asText();
                    JsonNode signedNode = voiceServiceWebClient.getSignedUrl(storageKey, null, null, null).block();
                    if (signedNode != null && signedNode.has("url")) {
                        return ResponseEntity.ok().body(java.util.Map.of("url", signedNode.get("url").asText()));
                    }
                    return ResponseEntity.ok().body(java.util.Map.of("storage_key", storageKey));
                } else {
                    return ResponseEntity.status(502).body(java.util.Map.of("error", "unsupported ref payload"));
                }
            }

            String storageKey = (String) row.get("storage_key");
            String ownerHex = (String) row.get("owner_hex");

            // 2) Permission check: validate JWT and compare owner
            String token = null;
            if (authorizationHeader != null && authorizationHeader.startsWith("Bearer ")) {
                token = authorizationHeader.substring(7);
            } else {
                // also check request attributes if filter populated
                HttpServletRequest req = ((ServletRequestAttributes) RequestContextHolder.getRequestAttributes()).getRequest();
                String h = req.getHeader("Authorization");
                if (h != null && h.startsWith("Bearer ")) token = h.substring(7);
            }

            if (token == null || token.isBlank()) {
                return ResponseEntity.status(401).body(java.util.Map.of("error", "missing token"));
            }

            try {
                var decoded = com.echoes.util.JwtUtil.verifyToken(jwtProperties.getUserSecretKey(), token);
                String claimUser = null;
                // try common claim keys
                if (decoded.getClaim("userId") != null && decoded.getClaim("userId").asString() != null) claimUser = decoded.getClaim("userId").asString();
                if (claimUser == null && decoded.getClaim("id") != null && decoded.getClaim("id").asString() != null) claimUser = decoded.getClaim("id").asString();
                if (claimUser == null && decoded.getSubject() != null) claimUser = decoded.getSubject();

                if (claimUser == null) {
                    log.warn("JWT did not contain identifiable user claim for audio access ref {}", refId);
                    return ResponseEntity.status(403).body(java.util.Map.of("error", "forbidden"));
                }
                String normalized = claimUser.replace("-", "").toLowerCase();
                String ownerNormalized = ownerHex != null ? ownerHex.toLowerCase() : null;
                if (ownerNormalized != null && !ownerNormalized.equals(normalized)) {
                    return ResponseEntity.status(403).body(java.util.Map.of("error", "forbidden"));
                }
            } catch (Exception e) {
                log.warn("JWT validation failed: {}", e.getMessage());
                return ResponseEntity.status(401).body(java.util.Map.of("error", "invalid token"));
            }

            // 3) Request voice-service to generate signed URL for this storage key
            try {
                JsonNode signedNode = voiceServiceWebClient.getSignedUrl(storageKey, null, null, null).block();
                if (signedNode != null && signedNode.has("url")) {
                    return ResponseEntity.ok(java.util.Map.of("url", signedNode.get("url").asText(), "storage_key", storageKey));
                } else if (signedNode != null && signedNode.has("storage_key")) {
                    return ResponseEntity.ok(java.util.Map.of("storage_key", signedNode.get("storage_key").asText()));
                }
            } catch (Exception e) {
                log.warn("Failed to get signed URL from voice service for storage_key {}: {}", storageKey, e.getMessage());
            }
            // fallback: return storage_key only
            return ResponseEntity.ok(java.util.Map.of("storage_key", storageKey));
        } catch (Exception e) {
            log.error("getAudioUrl error for ref {}: {}", refId, e.getMessage(), e);
            return ResponseEntity.status(500).body(java.util.Map.of("error", "internal"));
        }
    }
}


