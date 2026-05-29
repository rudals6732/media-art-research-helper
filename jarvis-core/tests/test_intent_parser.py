"""jarvis_agent.parse_intent() 유닛 테스트."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "jarvis-core"))

from src.jarvis_agent import parse_intent


class TestParseIntentStructured(unittest.TestCase):
    """구조화된 입력 파싱."""

    def test_search_structured(self):
        cmd, payload = parse_intent('search {"query": "미디어아트"}')
        self.assertEqual(cmd, "search")
        self.assertEqual(payload["query"], "미디어아트")

    def test_status_structured(self):
        cmd, payload = parse_intent("status {}")
        self.assertEqual(cmd, "status")

    def test_history_with_n(self):
        cmd, payload = parse_intent('history {"n": 5}')
        self.assertEqual(cmd, "history")
        self.assertEqual(payload["n"], 5)

    def test_pipeline_structured(self):
        cmd, payload = parse_intent('pipeline {"query": "생성 AI 예술"}')
        self.assertEqual(cmd, "pipeline")
        self.assertEqual(payload["query"], "생성 AI 예술")


class TestParseIntentNaturalLanguage(unittest.TestCase):
    """한국어 자연어 입력 인텐트 파싱."""

    # --- search ---
    def test_search_찾아줘(self):
        cmd, _ = parse_intent("미디어아트 논문 찾아줘")
        self.assertEqual(cmd, "search")

    def test_search_검색해줘(self):
        cmd, _ = parse_intent("인터랙티브 아트 검색해줘")
        self.assertEqual(cmd, "search")

    def test_search_query_extracted(self):
        _, payload = parse_intent("생성AI 미술 논문 찾아줘")
        self.assertIn("query", payload)
        self.assertTrue(len(payload["query"]) > 0)

    # --- report ---
    def test_report_만들어줘(self):
        cmd, _ = parse_intent("디지털 아트 보고서 만들어줘")
        self.assertEqual(cmd, "report")

    def test_report_작성(self):
        cmd, _ = parse_intent("미디어아트 리포트 작성해줘")
        self.assertEqual(cmd, "report")

    # --- pipeline ---
    def test_pipeline_자동(self):
        cmd, _ = parse_intent("자동으로 검색하고 보고서 만들어줘")
        self.assertEqual(cmd, "pipeline")

    def test_pipeline_한번에(self):
        cmd, _ = parse_intent("한번에 검색해서 보고서 만들어줘")
        self.assertEqual(cmd, "pipeline")

    # --- cite ---
    def test_cite_인용(self):
        cmd, _ = parse_intent("인용 형식 만들어줘")
        self.assertEqual(cmd, "cite")

    def test_cite_참고문헌(self):
        cmd, _ = parse_intent("참고문헌 생성해줘")
        self.assertEqual(cmd, "cite")

    # --- status ---
    def test_status_서버상태(self):
        cmd, _ = parse_intent("서버 상태 확인해줘")
        self.assertEqual(cmd, "status")

    def test_status_헬스체크(self):
        cmd, _ = parse_intent("헬스 체크해줘")
        self.assertEqual(cmd, "status")

    # --- history ---
    def test_history_이전(self):
        cmd, _ = parse_intent("이전 명령 기록 보여줘")
        self.assertEqual(cmd, "history")

    # --- save ---
    def test_save_저장(self):
        cmd, _ = parse_intent("결과 저장해줘")
        self.assertEqual(cmd, "save")


class TestParseIntentEdgeCases(unittest.TestCase):
    def test_empty_string_fallback(self):
        cmd, payload = parse_intent("")
        # 오류 없이 반환돼야 함
        self.assertIsInstance(cmd, str)
        self.assertIsInstance(payload, dict)

    def test_whitespace_only(self):
        cmd, payload = parse_intent("   ")
        self.assertIsInstance(cmd, str)

    def test_mixed_korean_english(self):
        cmd, _ = parse_intent("AI 미디어아트 논문 찾아줘")
        self.assertEqual(cmd, "search")

    def test_invalid_json_falls_back_to_nl(self):
        # JSON 파싱 실패 시 자연어로 폴백
        cmd, payload = parse_intent('search {invalid json}')
        self.assertIsInstance(cmd, str)
        self.assertIsInstance(payload, dict)


if __name__ == "__main__":
    unittest.main(verbosity=2)
