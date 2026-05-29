package com.project.model;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ReportSectionTest {

    @Test
    void defaultConstructorCreatesEmptySection() {
        ReportSection section = new ReportSection();
        assertNull(section.getType());
        assertNull(section.getHeading());
        assertNull(section.getContent());
    }

    @Test
    void allArgsConstructorSetsFields() {
        List<String> ids = List.of("RISS_001", "KCI_002");
        ReportSection section = new ReportSection(
            ReportSection.SectionType.INTRO,
            "서론",
            "미디어아트는 현대 예술의 핵심 분야이다.",
            ids
        );

        assertEquals(ReportSection.SectionType.INTRO, section.getType());
        assertEquals("서론", section.getHeading());
        assertEquals("미디어아트는 현대 예술의 핵심 분야이다.", section.getContent());
        assertEquals(2, section.getCitationIds().size());
    }

    @Test
    void sectionTypeEnumHasAllValues() {
        ReportSection.SectionType[] types = ReportSection.SectionType.values();
        assertEquals(4, types.length);

        List<String> names = List.of("INTRO", "BODY", "CONCLUSION", "REFERENCES");
        for (ReportSection.SectionType t : types) {
            assertTrue(names.contains(t.name()), "예상치 못한 타입: " + t.name());
        }
    }

    @Test
    void emptyCitationIdsAllowed() {
        ReportSection section = new ReportSection(
            ReportSection.SectionType.CONCLUSION,
            "결론",
            "본 연구를 통해 다음을 확인하였다.",
            List.of()
        );
        assertNotNull(section.getCitationIds());
        assertTrue(section.getCitationIds().isEmpty());
    }

    @Test
    void settersUpdateFields() {
        ReportSection section = new ReportSection();
        section.setType(ReportSection.SectionType.BODY);
        section.setHeading("본론");
        section.setContent("내용 본문");
        section.setCitationIds(List.of("RISS_999"));

        assertEquals(ReportSection.SectionType.BODY, section.getType());
        assertEquals("본론", section.getHeading());
        assertEquals(1, section.getCitationIds().size());
    }
}
