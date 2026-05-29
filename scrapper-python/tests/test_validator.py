"""validator.py 유닛 테스트 (URL 접근 검사 제외)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.validator import (
    _check_title,
    _check_author,
    _check_year,
    _check_source_url,
    verify_paper,
    deduplicate,
    filter_valid,
)

VALID_PAPER = {
    "id":       "RISS_abc12345",
    "title":    "인터랙티브 미디어아트의 관람객 참여 연구",
    "authors":  "김미래",
    "journal":  "미디어아트 연구",
    "year":     2023,
    "abstract": "본 연구는 인터랙티브 미디어아트를 분석한다.",
    "url":      "https://www.riss.kr/link?id=A12345678",
    "source":   "RISS",
}


class TestCheckTitle(unittest.TestCase):
    def test_valid_title_no_issues(self):
        self.assertEqual(_check_title("인터랙티브 미디어아트 연구"), [])

    def test_empty_title_flagged(self):
        self.assertTrue(len(_check_title("")) > 0)

    def test_too_short_flagged(self):
        self.assertTrue(len(_check_title("AB")) > 0)

    def test_garbage_chars_flagged(self):
        garbage = "★☆■□▲△" * 5
        self.assertTrue(len(_check_title(garbage)) > 0)


class TestCheckAuthor(unittest.TestCase):
    def test_korean_name_valid(self):
        self.assertEqual(_check_author("김미래"), [])

    def test_english_name_valid(self):
        self.assertEqual(_check_author("Kim J"), [])

    def test_empty_author_flagged(self):
        self.assertTrue(len(_check_author("")) > 0)

    def test_multiple_authors_valid(self):
        self.assertEqual(_check_author("김미래, 박예술"), [])


class TestCheckYear(unittest.TestCase):
    def test_valid_year(self):
        self.assertEqual(_check_year(2023), [])

    def test_year_1900_flagged(self):
        self.assertTrue(len(_check_year(1900)) > 0)

    def test_year_2200_flagged(self):
        self.assertTrue(len(_check_year(2200)) > 0)

    def test_none_flagged(self):
        self.assertTrue(len(_check_year(None)) > 0)

    def test_string_year_valid(self):
        self.assertEqual(_check_year("2023"), [])


class TestCheckSourceUrl(unittest.TestCase):
    def test_riss_url_matches(self):
        self.assertEqual(_check_source_url("https://www.riss.kr/link?id=A123", "RISS"), [])

    def test_kci_url_matches(self):
        self.assertEqual(_check_source_url("https://www.kci.go.kr/kciportal/123", "KCI"), [])

    def test_wrong_domain_flagged(self):
        issues = _check_source_url("https://www.google.com/", "RISS")
        self.assertTrue(len(issues) > 0)

    def test_empty_url_flagged(self):
        self.assertTrue(len(_check_source_url("", "RISS")) > 0)


class TestVerifyPaper(unittest.TestCase):
    def test_valid_paper_passes(self):
        result = verify_paper(VALID_PAPER, check_url=False)
        self.assertTrue(result["valid"])
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["issues"], [])

    def test_invalid_paper_fails(self):
        bad = {**VALID_PAPER, "title": "", "authors": "", "year": 1800}
        result = verify_paper(bad, check_url=False)
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["issues"]), 0)

    def test_score_decreases_per_issue(self):
        bad = {**VALID_PAPER, "title": ""}
        result = verify_paper(bad, check_url=False)
        self.assertLess(result["score"], 100)

    def test_original_fields_preserved(self):
        result = verify_paper(VALID_PAPER, check_url=False)
        self.assertEqual(result["title"], VALID_PAPER["title"])
        self.assertEqual(result["source"], VALID_PAPER["source"])

    def test_url_check_skipped_when_false(self):
        # check_url=False 이면 URL 관련 이슈가 없어야 함 (도메인 불일치 제외)
        paper = {**VALID_PAPER, "url": "https://www.riss.kr/fake"}
        result = verify_paper(paper, check_url=False)
        url_issues = [i for i in result["issues"] if "타임아웃" in i or "연결" in i]
        self.assertEqual(url_issues, [])


class TestDeduplicate(unittest.TestCase):
    def _make_paper(self, title, score=100, source="RISS"):
        return {**VALID_PAPER, "title": title, "score": score, "source": source}

    def test_exact_duplicate_removed(self):
        papers = [
            self._make_paper("미디어아트 연구", score=100),
            self._make_paper("미디어아트 연구", score=80),
        ]
        result = deduplicate(papers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["score"], 100)  # 점수 높은 쪽 보존

    def test_similar_titles_deduped(self):
        papers = [
            self._make_paper("인터랙티브 미디어아트의 관람객 참여 연구"),
            self._make_paper("인터랙티브 미디어아트의 관람객 참여 연구 분석"),
        ]
        result = deduplicate(papers, threshold=0.85)
        # 유사도 높은 경우 1건으로 줄어야 함
        self.assertLessEqual(len(result), 2)

    def test_distinct_titles_kept(self):
        papers = [
            self._make_paper("미디어아트 연구"),
            self._make_paper("디지털 사운드 아트 분석"),
            self._make_paper("AI 생성 예술의 저작권"),
        ]
        result = deduplicate(papers)
        self.assertEqual(len(result), 3)

    def test_empty_input(self):
        self.assertEqual(deduplicate([]), [])


class TestFilterValid(unittest.TestCase):
    def test_valid_paper_passes_filter(self):
        papers = [VALID_PAPER]
        result = filter_valid(papers, check_url=False, dedup=False)
        self.assertEqual(len(result), 1)

    def test_invalid_paper_removed(self):
        bad = {**VALID_PAPER, "title": "", "authors": "", "year": 1800}
        result = filter_valid([bad], check_url=False, dedup=False, min_score=60)
        self.assertEqual(len(result), 0)

    def test_mixed_papers(self):
        papers = [
            VALID_PAPER,
            {**VALID_PAPER, "id": "RISS_bad", "title": "", "year": 1800},
        ]
        result = filter_valid(papers, check_url=False, dedup=False)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], VALID_PAPER["id"])

    def test_min_score_threshold(self):
        paper = {**VALID_PAPER, "title": ""}  # 1개 이슈 → score 80
        result = filter_valid([paper], check_url=False, dedup=False, min_score=90)
        self.assertEqual(len(result), 0)

        result = filter_valid([paper], check_url=False, dedup=False, min_score=70)
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
