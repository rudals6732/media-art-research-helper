package com.project.service;

import com.project.model.Paper;
import com.project.model.ReportSection;
import com.project.model.ReportSection.SectionType;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class ReportService {

    /**
     * 수집된 논문 목록으로부터 보고서 초안(서론/본론/결론/참고문헌)을 구성한다.
     */
    public List<ReportSection> buildReport(String topic, List<Paper> papers) {
        List<ReportSection> sections = new ArrayList<>();

        sections.add(buildIntro(topic, papers));
        sections.add(buildBody(topic, papers));
        sections.add(buildConclusion(topic));
        sections.add(buildReferences(papers));

        return sections;
    }

    private ReportSection buildIntro(String topic, List<Paper> papers) {
        // TODO: Claude API 또는 템플릿 기반 서론 생성
        String content = String.format(
            "%s 분야는 현대 예술과 기술의 교차점에서 중요한 위치를 차지하고 있다. " +
            "본 보고서는 총 %d편의 선행 연구를 바탕으로 해당 주제를 분석한다.",
            topic, papers.size()
        );
        List<String> ids = papers.stream().map(Paper::getId).limit(2).toList();
        return new ReportSection(SectionType.INTRO, "서론", content, ids);
    }

    private ReportSection buildBody(String topic, List<Paper> papers) {
        // TODO: 논문 초록 기반 본론 자동 구성
        StringBuilder sb = new StringBuilder();
        for (Paper p : papers) {
            sb.append(String.format("[%s] %s\n\n", p.getSource(), p.getAbstractText()));
        }
        List<String> ids = papers.stream().map(Paper::getId).toList();
        return new ReportSection(SectionType.BODY, "본론", sb.toString().trim(), ids);
    }

    private ReportSection buildConclusion(String topic) {
        // TODO: 요약 및 시사점 자동 생성
        String content = topic + "에 관한 선행 연구를 종합한 결과, 향후 연구 방향으로 ...";
        return new ReportSection(SectionType.CONCLUSION, "결론", content, List.of());
    }

    private ReportSection buildReferences(List<Paper> papers) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < papers.size(); i++) {
            Paper p = papers.get(i);
            sb.append(String.format("%d. %s. (%d). %s. %s. %s\n",
                i + 1, p.getAuthors(), p.getYear(), p.getTitle(), p.getJournal(), p.getUrl()));
        }
        return new ReportSection(SectionType.REFERENCES, "참고문헌", sb.toString().trim(), List.of());
    }
}
