package com.project.model;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PaperTest {

    @Test
    void defaultConstructorCreatesEmptyPaper() {
        Paper paper = new Paper();
        assertNull(paper.getId());
        assertNull(paper.getTitle());
        assertEquals(0, paper.getYear());
    }

    @Test
    void allArgsConstructorSetsFields() {
        Paper paper = new Paper(
            "RISS_abc123", "인터랙티브 미디어아트 연구",
            "김미래", "미디어아트 연구", 2023,
            "본 연구는 인터랙티브 미디어아트를 분석한다.",
            "https://www.riss.kr/link?id=A12345678", "RISS"
        );
        assertEquals("RISS_abc123", paper.getId());
        assertEquals("인터랙티브 미디어아트 연구", paper.getTitle());
        assertEquals("김미래", paper.getAuthors());
        assertEquals("미디어아트 연구", paper.getJournal());
        assertEquals(2023, paper.getYear());
        assertEquals("RISS", paper.getSource());
    }

    @Test
    void settersUpdateFields() {
        Paper paper = new Paper();
        paper.setId("KCI_xyz789");
        paper.setTitle("디지털 사운드 아트");
        paper.setYear(2024);
        paper.setSource("KCI");

        assertEquals("KCI_xyz789", paper.getId());
        assertEquals("디지털 사운드 아트", paper.getTitle());
        assertEquals(2024, paper.getYear());
        assertEquals("KCI", paper.getSource());
    }

    @Test
    void abstractTextCanBeEmpty() {
        Paper paper = new Paper();
        paper.setAbstractText("");
        assertEquals("", paper.getAbstractText());
    }

    @Test
    void urlCanBeNull() {
        Paper paper = new Paper();
        paper.setUrl(null);
        assertNull(paper.getUrl());
    }
}
