"""text_processor.py 유닛 테스트."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.text_processor import (
    clean_text,
    extract_sentences,
    extract_keywords,
    paraphrase,
    generate_citation,
    text_stats,
    process_abstract,
)

SAMPLE_ABSTRACT = (
    "미디어아트는 현대 예술과 기술의 교차점에서 발전하고 있다. "
    "연구자들은 인터랙티브 설치 작품을 분석하여 관람객과의 상호작용 방법을 연구한다. "
    "본 연구는 디지털 기술을 활용한 미디어아트의 효과를 분석하고 새로운 방법을 제안한다. "
    "결과적으로, 인터랙티브 작품은 관람객 참여를 높이는 효과가 있었다."
)

SAMPLE_PAPER = {
    "title":   "인터랙티브 미디어아트의 관람객 참여 분석",
    "authors": "김미래, 박예술",
    "journal": "미디어아트 연구",
    "year":    2024,
    "url":     "https://www.kci.go.kr/example/12345",
    "source":  "KCI",
}


class TestCleanText(unittest.TestCase):
    def test_removes_html_tags(self):
        result = clean_text("<p>미디어아트 <b>연구</b></p>")
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertIn("미디어아트", result)

    def test_decodes_html_entities(self):
        result = clean_text("연구 &amp; 분석 &lt;2024&gt;")
        # clean_text decodes entities then strips non-alphanumeric chars like &
        self.assertNotIn("&amp;", result)
        self.assertNotIn("&lt;", result)

    def test_normalizes_whitespace(self):
        result = clean_text("미디어   아트\t연구\n\n분석")
        self.assertNotIn("   ", result)
        self.assertNotIn("\t", result)

    def test_empty_input(self):
        self.assertEqual(clean_text(""), "")

    def test_plain_text_unchanged(self):
        plain = "미디어아트 연구 결과"
        self.assertEqual(clean_text(plain), plain)


class TestExtractSentences(unittest.TestCase):
    def test_splits_korean_sentences(self):
        sentences = extract_sentences(SAMPLE_ABSTRACT)
        self.assertGreater(len(sentences), 1)

    def test_each_sentence_nonempty(self):
        for s in extract_sentences(SAMPLE_ABSTRACT):
            self.assertGreater(len(s.strip()), 0)

    def test_filters_short_fragments(self):
        text = "미디어. 아트. 인터랙티브 미디어아트는 현대 예술 분야이다."
        sentences = extract_sentences(text)
        for s in sentences:
            self.assertGreater(len(s), 8)

    def test_empty_input(self):
        self.assertEqual(extract_sentences(""), [])


class TestExtractKeywords(unittest.TestCase):
    def test_returns_list(self):
        kws = extract_keywords(SAMPLE_ABSTRACT)
        self.assertIsInstance(kws, list)

    def test_top_n_respected(self):
        kws = extract_keywords(SAMPLE_ABSTRACT, top_n=5)
        self.assertLessEqual(len(kws), 5)

    def test_stopwords_excluded(self):
        stopwords = {"이", "그", "저", "및", "등", "또한", "따라서"}
        kws = extract_keywords(SAMPLE_ABSTRACT)
        for kw in kws:
            self.assertNotIn(kw, stopwords)

    def test_domain_keywords_present(self):
        kws = extract_keywords(SAMPLE_ABSTRACT)
        found = any(k in ("미디어아트", "인터랙티브", "연구") for k in kws)
        self.assertTrue(found, f"도메인 키워드 없음: {kws}")


class TestParaphrase(unittest.TestCase):
    def test_returns_string(self):
        result = paraphrase(SAMPLE_ABSTRACT)
        self.assertIsInstance(result, str)

    def test_output_nonempty(self):
        self.assertGreater(len(paraphrase(SAMPLE_ABSTRACT)), 0)

    def test_synonym_applied(self):
        text = "연구자들이 분석 방법을 활용하여 결과를 제안한다."
        result = paraphrase(text)
        # 동의어 중 하나 이상이 적용됐어야 함
        changed = result != text
        self.assertTrue(changed, "패러프레이즈 변환 없음")

    def test_preserves_meaning_words(self):
        text = "미디어아트 연구 분석"
        result = paraphrase(text)
        # 의미 핵심어(예: '미디어')는 보존
        self.assertTrue("미디어" in result or "예술" in result)


class TestGenerateCitation(unittest.TestCase):
    def test_apa_format(self):
        cit = generate_citation(SAMPLE_PAPER, "APA")
        self.assertIn("2024", cit)
        self.assertIn("김미래", cit)
        self.assertIn("인터랙티브", cit)

    def test_mla_format(self):
        cit = generate_citation(SAMPLE_PAPER, "MLA")
        self.assertIn("2024", cit)
        self.assertIn('"', cit)

    def test_kci_format(self):
        cit = generate_citation(SAMPLE_PAPER, "KCI")
        self.assertIn("(2024)", cit)
        self.assertIn("미디어아트 연구", cit)

    def test_unknown_style_raises(self):
        with self.assertRaises(ValueError):
            generate_citation(SAMPLE_PAPER, "CHICAGO")


class TestTextStats(unittest.TestCase):
    def test_returns_all_keys(self):
        stats = text_stats(SAMPLE_ABSTRACT)
        for key in ("char_count", "word_count", "sentence_count", "avg_sentence_length"):
            self.assertIn(key, stats)

    def test_positive_counts(self):
        stats = text_stats(SAMPLE_ABSTRACT)
        self.assertGreater(stats["char_count"], 0)
        self.assertGreater(stats["word_count"], 0)

    def test_empty_input(self):
        stats = text_stats("")
        self.assertEqual(stats["char_count"], 0)
        self.assertEqual(stats["avg_sentence_length"], 0)


class TestProcessAbstract(unittest.TestCase):
    def test_all_keys_present(self):
        result = process_abstract(SAMPLE_ABSTRACT)
        for key in ("cleaned", "sentences", "keywords", "paraphrased", "stats"):
            self.assertIn(key, result)

    def test_with_paper_adds_citations(self):
        result = process_abstract(SAMPLE_ABSTRACT, paper=SAMPLE_PAPER)
        self.assertIn("citations", result)
        self.assertIn("APA", result["citations"])
        self.assertIn("MLA", result["citations"])
        self.assertIn("KCI", result["citations"])

    def test_without_paper_no_citations(self):
        result = process_abstract(SAMPLE_ABSTRACT)
        self.assertNotIn("citations", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
