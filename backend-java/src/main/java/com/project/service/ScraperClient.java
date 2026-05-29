package com.project.service;

import com.project.model.Paper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

@Service
public class ScraperClient {

    private static final Logger log = LoggerFactory.getLogger(ScraperClient.class);

    private final String baseUrl;
    private final HttpClient http;
    private final ObjectMapper mapper;

    public ScraperClient(
            @Value("${scrapper.base-url}") String baseUrl,
            ObjectMapper mapper) {
        this.baseUrl = baseUrl;
        this.mapper  = mapper;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    /**
     * Python 스크래퍼의 /search 엔드포인트를 호출해 논문 목록을 반환한다.
     *
     * @param query    검색어
     * @param limit    최대 결과 건수
     * @param checkUrl URL 접근성 검사 여부 (느림)
     * @param dedup    중복 제거 여부
     * @param minScore 최소 통과 점수 (0~100)
     */
    public List<Paper> search(
            String query, int limit, boolean checkUrl, boolean dedup, int minScore)
            throws IOException, InterruptedException {

        Map<String, Object> body = Map.of(
                "query",     query,
                "limit",     limit,
                "check_url", checkUrl,
                "dedup",     dedup,
                "min_score", minScore
        );

        String requestBody = mapper.writeValueAsString(body);
        log.info("ScraperClient.search → {}/search  query={}", baseUrl, query);

        HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/search"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .timeout(Duration.ofSeconds(30))
                .build();

        HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());

        if (resp.statusCode() != 200) {
            throw new IOException(
                    "스크래퍼 응답 오류: HTTP " + resp.statusCode() + " — " + resp.body());
        }

        List<Map<String, Object>> raw =
                mapper.readValue(resp.body(), new TypeReference<>() {});

        return raw.stream().map(this::mapToPaper).toList();
    }

    /** 스크래퍼 헬스 체크 */
    public boolean isHealthy() {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + "/health"))
                    .GET()
                    .timeout(Duration.ofSeconds(5))
                    .build();
            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            return resp.statusCode() == 200;
        } catch (Exception e) {
            log.warn("스크래퍼 헬스 체크 실패: {}", e.getMessage());
            return false;
        }
    }

    private Paper mapToPaper(Map<String, Object> m) {
        Paper p = new Paper();
        p.setId(str(m, "id"));
        p.setTitle(str(m, "title"));
        p.setAuthors(str(m, "authors"));
        p.setJournal(str(m, "journal"));
        p.setYear(m.get("year") instanceof Number n ? n.intValue() : 0);
        p.setAbstractText(str(m, "abstract"));
        p.setUrl(str(m, "url"));
        p.setSource(str(m, "source"));
        return p;
    }

    private static String str(Map<String, Object> m, String key) {
        Object v = m.get(key);
        return v != null ? v.toString() : "";
    }
}
