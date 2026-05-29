package com.project.controller;

import com.project.model.Paper;
import com.project.model.ReportSection;
import com.project.service.ReportService;
import com.project.service.ScraperClient;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class PaperController {

    private final ReportService reportService;
    private final ScraperClient scraperClient;

    public PaperController(ReportService reportService, ScraperClient scraperClient) {
        this.reportService = reportService;
        this.scraperClient = scraperClient;
    }

    /**
     * 논문 목록 수신 후 보고서 초안 반환.
     *
     * Request body: { "topic": "...", "papers": [...] }
     * papers 가 비어 있거나 생략된 경우 Python 스크래퍼에서 자동 검색.
     */
    @PostMapping("/report")
    public ResponseEntity<?> generateReport(@RequestBody ReportRequest req) {
        if (req.getTopic() == null || req.getTopic().isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "topic 파라미터가 필요합니다"));
        }

        List<Paper> papers = req.getPapers();

        if (papers == null || papers.isEmpty()) {
            try {
                papers = scraperClient.search(req.getTopic(), 10, false, true, 60);
            } catch (Exception e) {
                return ResponseEntity.internalServerError()
                        .body(Map.of("error", "스크래퍼 호출 실패: " + e.getMessage()));
            }
        }

        return ResponseEntity.ok(reportService.buildReport(req.getTopic(), papers));
    }

    /**
     * Python 스크래퍼 검색을 Java에서 직접 프록시하는 엔드포인트.
     *
     * Request body: { "query": "...", "limit": 10, "check_url": false, "dedup": true, "min_score": 60 }
     */
    @PostMapping("/search")
    public ResponseEntity<?> search(@RequestBody Map<String, Object> body) {
        String query = (String) body.getOrDefault("query", "");
        if (query.isBlank()) {
            return ResponseEntity.badRequest().body(Map.of("error", "query 파라미터가 필요합니다"));
        }

        int limit      = intVal(body, "limit",     10);
        boolean checkUrl = boolVal(body, "check_url", false);
        boolean dedup    = boolVal(body, "dedup",     true);
        int minScore   = intVal(body, "min_score",  60);

        try {
            List<Paper> papers = scraperClient.search(query, limit, checkUrl, dedup, minScore);
            return ResponseEntity.ok(papers);
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                    .body(Map.of("error", "검색 실패: " + e.getMessage()));
        }
    }

    /** 헬스 체크 (Java 백엔드 + Python 스크래퍼 상태 포함) */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
                "backend", "ok",
                "scraper", scraperClient.isHealthy() ? "ok" : "unreachable"
        ));
    }

    // -------------------------------------------------------------------------

    private static int intVal(Map<String, Object> m, String key, int def) {
        Object v = m.get(key);
        return v instanceof Number n ? n.intValue() : def;
    }

    private static boolean boolVal(Map<String, Object> m, String key, boolean def) {
        Object v = m.get(key);
        if (v instanceof Boolean b) return b;
        if (v instanceof String s)  return Boolean.parseBoolean(s);
        return def;
    }
}
