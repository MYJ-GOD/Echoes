package com.echoes.rag.domain.knowledge.controller;

import com.echoes.rag.domain.knowledge.entity.KnowledgeBase;
import com.echoes.rag.domain.knowledge.service.KnowledgeBaseService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/rag/knowledge-bases")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Knowledge Base", description = "Knowledge Base Management API")
public class KnowledgeBaseController {

    private final KnowledgeBaseService knowledgeBaseService;

    @GetMapping
    @Operation(summary = "List knowledge bases")
    public ResponseEntity<?> list(
            @RequestParam(value = "userId", required = false) String userId,
            @RequestParam(value = "includePublic", defaultValue = "false") boolean includePublic,
            @RequestParam(value = "includeDeleted", defaultValue = "false") boolean includeDeleted
    ) {
        try {
            if (includePublic) {
                List<KnowledgeBase> publicList = knowledgeBaseService.listPublic();
                if (userId != null) {
                    List<KnowledgeBase> userList = knowledgeBaseService.listByUser(userId, includeDeleted);
                    publicList.addAll(userList);
                }
                return ResponseEntity.ok(publicList);
            }

            if (userId != null) {
                return ResponseEntity.ok(knowledgeBaseService.listByUser(userId, includeDeleted));
            }

            return ResponseEntity.ok(knowledgeBaseService.listPublic());
        } catch (Exception e) {
            log.error("knowledge-bases list failed, userId={}, includePublic={}, includeDeleted={}",
                    userId, includePublic, includeDeleted, e);
            Map<String, Object> error = new HashMap<>();
            error.put("error", "KNOWLEDGE_BASE_LIST_FAILED");
            error.put("message", e.getMessage());
            return ResponseEntity.internalServerError().body(error);
        }
    }

    @GetMapping("/{kbId}")
    @Operation(summary = "Get knowledge base")
    public ResponseEntity<KnowledgeBase> get(@PathVariable String kbId) {
        KnowledgeBase kb = knowledgeBaseService.getById(kbId);
        if (kb == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(kb);
    }

    @PostMapping
    @Operation(summary = "Create knowledge base")
    public ResponseEntity<KnowledgeBase> create(@RequestBody KnowledgeBase knowledgeBase) {
        KnowledgeBase created = knowledgeBaseService.create(knowledgeBase);
        return ResponseEntity.ok(created);
    }

    @PutMapping("/{kbId}")
    @Operation(summary = "Update knowledge base")
    public ResponseEntity<KnowledgeBase> update(
            @PathVariable String kbId,
            @RequestBody KnowledgeBase knowledgeBase
    ) {
        KnowledgeBase updated = knowledgeBaseService.update(kbId, knowledgeBase);
        if (updated == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(updated);
    }

    @DeleteMapping("/{kbId}")
    @Operation(summary = "Delete knowledge base")
    public ResponseEntity<Void> delete(@PathVariable String kbId) {
        knowledgeBaseService.delete(kbId);
        return ResponseEntity.ok().build();
    }
}
