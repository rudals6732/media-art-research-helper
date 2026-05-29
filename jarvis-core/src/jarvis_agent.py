"""JARVIS 오케스트레이터 — 시스템 명령어 해석 및 워크플로우 통제 컨트롤러.

아키텍처
  사용자 입력 (텍스트 or 음성)
       │
       ▼
  parse_intent()  ← 한국어 자연어 → (command, payload) 변환
       │
       ▼
  execute()       ← 구조화된 명령 디스패처
       │
  ┌────┴──────────────────────────────────┐
  ▼         ▼         ▼         ▼         ▼
search   report    pipeline   run      status
  │         │         │
scraper  backend  scraper→backend 연쇄

세션 관리
  - _history : 최근 명령/결과 50건 보존
  - _last_papers : 마지막 검색 결과 (pipeline 연쇄에 재사용)
"""

import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .os_bridge import OsBridge
from .voice_handler import VoiceHandler

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"
_MAX_HISTORY = 50


def _load_cfg() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 한국어 자연어 인텐트 파서
# ---------------------------------------------------------------------------

# (정규식, 명령어) 우선순위 순 목록
_INTENT_RULES: list[tuple[re.Pattern, str]] = [
    # pipeline — search 보다 먼저 검사
    (re.compile(r"(자동|한\s*번에|통합|전체).*(검색|보고서|리포트)"), "pipeline"),
    (re.compile(r"(검색|찾아).*(보고서|리포트).*(만들|작성|생성)"), "pipeline"),
    # search
    (re.compile(r"(찾아|검색|탐색|조회)"), "search"),
    (re.compile(r"논문.*(보여|알려)"), "search"),
    # report
    (re.compile(r"(보고서|리포트).*(만들|작성|생성|써)"), "report"),
    # cite
    (re.compile(r"(인용|출처|참고문헌).*(만들|형식|생성|뽑)"), "cite"),
    # save
    (re.compile(r"(저장|파일로|출력)"), "save"),
    # status
    (re.compile(r"(상태|헬스|연결|서버).*(확인|체크|점검|봐)"), "status"),
    (re.compile(r"(확인|체크).*(서버|상태)"), "status"),
    # history
    (re.compile(r"(이전|기록|히스토리|최근\s*명령)"), "history"),
    # run
    (re.compile(r"(실행|구동|시작).*(스크래퍼|크롤러|서버|백엔드)"), "run"),
    # speak
    (re.compile(r"(말해|읽어|발화)"), "speak"),
]

# 인텐트 추출 시 제거할 기능어 집합
_FUNC_WORDS = frozenset({
    "논문", "찾아줘", "찾아", "검색해줘", "검색해", "보여줘", "보여",
    "알려줘", "알려", "관련", "에", "대한", "의", "를", "을", "이", "가",
    "좀", "해줘", "해", "주세요", "주십시오", "제발", "부탁", "해주세요",
})


def _extract_query(text: str) -> str:
    """자연어 문장에서 검색 토픽을 추출."""
    tokens = text.split()
    filtered = [t for t in tokens if t not in _FUNC_WORDS and len(t) > 1]
    return " ".join(filtered).strip()


def parse_intent(text: str) -> tuple[str, dict]:
    """한국어 자연어 텍스트를 (command, payload) 로 변환.

    구조화된 입력("search {...}") 이면 그대로 파싱.
    자연어 입력이면 인텐트 규칙을 적용.

    Returns:
        (command_str, payload_dict)
    """
    text = text.strip()

    # 구조화된 입력: "search {"query": "미디어아트"}"
    structured = re.match(r"^(\w+)\s+(\{.*\})$", text, re.S)
    if structured:
        cmd = structured.group(1).lower()
        try:
            payload = json.loads(structured.group(2))
            return cmd, payload
        except json.JSONDecodeError:
            pass

    # 자연어 인텐트 매칭
    for pattern, command in _INTENT_RULES:
        if pattern.search(text):
            query = _extract_query(text)
            payload: dict = {}
            if command in ("search", "pipeline"):
                payload["query"] = query
            elif command == "report":
                payload["topic"] = query
            elif command == "speak":
                payload["text"] = text
            elif command == "save":
                payload["filename"] = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return command, payload

    # 폴백: 첫 단어를 명령어로, 나머지를 query로
    parts = text.split(maxsplit=1)
    if not parts:
        return "help", {}
    return parts[0].lower(), {"query": parts[1]} if len(parts) > 1 else {}


# ---------------------------------------------------------------------------
# HTTP 클라이언트 (재시도 내장)
# ---------------------------------------------------------------------------

def _make_http_session(retries: int = 3) -> requests.Session:
    """지수 백오프 재시도가 설정된 requests.Session 반환."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.8,          # 0.8 → 1.6 → 3.2초
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ---------------------------------------------------------------------------
# 메인 에이전트
# ---------------------------------------------------------------------------

class JarvisAgent:
    """사용자 명령을 받아 적절한 하위 시스템에 위임하는 오케스트레이터."""

    def __init__(self):
        cfg = _load_cfg()

        self._scraper_url          = cfg["scraper"]["base_url"]
        self._scraper_health_path  = cfg["scraper"].get("health_path", "/health")
        self._backend_url          = cfg["backend"]["base_url"]
        self._backend_health_path  = cfg["backend"].get("health_path", "/health")
        self._timeout              = cfg["scraper"].get("timeout_sec", 30)
        self._max_retries = cfg["agent"].get("max_retries", 3)

        self._http    = _make_http_session(self._max_retries)
        self._os      = OsBridge()
        self._voice   = VoiceHandler(language=cfg["voice"].get("language", "ko-KR"))
        self._voice_enabled = cfg["voice"].get("enabled", False)

        # 세션 상태
        self._history: list[dict]    = []   # 최근 명령/결과 기록
        self._last_papers: list[dict] = []  # 마지막 검색 결과 (pipeline 재사용)

        logging.basicConfig(
            level=getattr(logging, cfg["agent"].get("log_level", "INFO")),
            format="%(levelname)s %(name)s — %(message)s",
        )

    # ------------------------------------------------------------------
    # 공개 진입점
    # ------------------------------------------------------------------

    def execute(self, command: str, payload: dict | None = None) -> Any:
        """명령어 + payload를 받아 해당 핸들러에 위임하고 결과를 반환.

        히스토리에 자동 기록되며, 오류 발생 시 {"error": ...} dict를 반환.
        """
        payload = payload or {}
        logger.info("명령: %s | payload=%s", command, payload)

        handlers: dict[str, Any] = {
            "search":   self._handle_search,
            "report":   self._handle_report,
            "cite":     self._handle_cite,
            "pipeline": self._handle_pipeline,
            "run":      self._handle_run,
            "speak":    self._handle_speak,
            "status":   self._handle_status,
            "save":     self._handle_save,
            "history":  self._handle_history,
        }

        handler = handlers.get(command.lower())
        if handler is None:
            return {
                "error": f"알 수 없는 명령어: '{command}'",
                "available": list(handlers),
            }

        start = time.monotonic()
        try:
            result = handler(payload)
        except requests.ConnectionError as exc:
            result = {"error": f"서버 연결 실패: {exc}"}
        except requests.Timeout:
            result = {"error": f"요청 타임아웃 ({self._timeout}s)"}
        except PermissionError as exc:
            result = {"error": f"권한 거부: {exc}"}
        except Exception as exc:
            logger.exception("명령 실행 오류 (%s)", command)
            result = {"error": str(exc)}

        elapsed = round(time.monotonic() - start, 2)
        self._record_history(command, payload, result, elapsed)
        return result

    def run_interactive(self) -> None:
        """대화형 루프 — 텍스트/음성 입력을 받아 execute() 호출."""
        self._say("자비스 시스템 온라인. '종료' 또는 Ctrl+C로 종료합니다.")
        self._print_help()

        while True:
            try:
                raw = self._listen_or_input("\nJARVIS> ").strip()
                if not raw:
                    continue
                if raw.lower() in ("exit", "quit", "종료", "q"):
                    self._say("시스템을 종료합니다.")
                    break
                if raw.lower() in ("help", "도움말", "?"):
                    self._print_help()
                    continue

                command, payload = parse_intent(raw)
                result = self.execute(command, payload)
                self._print_result(result)

            except KeyboardInterrupt:
                print()
                self._say("시스템을 종료합니다.")
                break

    # ------------------------------------------------------------------
    # 핸들러 — 검색 / 보고서 / 인용
    # ------------------------------------------------------------------

    def _handle_search(self, payload: dict) -> dict:
        """논문 검색: Python scraper POST /search.

        payload 키:
          query     (필수) 검색어
          limit     건수 (기본 10)
          check_url URL 접근성 검사 (기본 true)
          dedup     중복 제거 (기본 true)
          min_score 최소 통과 점수 (기본 60)
        """
        if not payload.get("query"):
            return {"error": "query 파라미터가 필요합니다"}

        resp = self._http.post(
            f"{self._scraper_url}/search",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        papers = resp.json()
        self._last_papers = papers   # pipeline 연쇄용 저장
        return {"count": len(papers), "papers": papers}

    def _handle_report(self, payload: dict) -> dict:
        """보고서 생성: Java backend POST /api/report.

        payload 키:
          topic  (필수) 보고서 주제
          papers 논문 리스트 (없으면 _last_papers 재사용)
        """
        if not payload.get("topic"):
            return {"error": "topic 파라미터가 필요합니다"}

        if not payload.get("papers"):
            if not self._last_papers:
                return {"error": "논문 데이터 없음. 먼저 search를 실행하세요."}
            payload = {**payload, "papers": self._last_papers}

        resp = self._http.post(
            f"{self._backend_url}/api/report",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _handle_cite(self, payload: dict) -> dict:
        """인용 형식 생성: Python scraper POST /cite.

        payload 키:
          paper  논문 dict (없으면 _last_papers[0] 재사용)
          styles 형식 리스트 (기본 ["APA","MLA","KCI"])
        """
        if not payload.get("paper"):
            if not self._last_papers:
                return {"error": "논문 데이터 없음. 먼저 search를 실행하세요."}
            payload = {**payload, "paper": self._last_papers[0]}

        resp = self._http.post(
            f"{self._scraper_url}/cite",
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # 핸들러 — 파이프라인 (search → report 연쇄)
    # ------------------------------------------------------------------

    def _handle_pipeline(self, payload: dict) -> dict:
        """논문 검색 → 보고서 생성을 한 번에 수행.

        payload 키:
          query  (필수) 검색어 겸 보고서 주제
          limit  검색 건수 (기본 10)
        """
        query = payload.get("query", "")
        if not query:
            return {"error": "query 파라미터가 필요합니다"}

        self._say(f"'{query}' 파이프라인 시작: 검색 중...")
        search_result = self._handle_search(payload)
        if "error" in search_result:
            return {"pipeline_error": "검색 실패", **search_result}

        papers = search_result.get("papers", [])
        if not papers:
            return {"pipeline_error": "검색 결과 없음", "search": search_result}

        self._say(f"{len(papers)}건 수집 완료. 보고서 생성 중...")
        report_result = self._handle_report({"topic": query, "papers": papers})

        # 자동 저장
        filename = f"pipeline_{query[:20]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        save_result = self._handle_save({"data": report_result, "filename": filename})

        self._say("파이프라인 완료.")
        return {
            "search":  search_result,
            "report":  report_result,
            "saved":   save_result,
        }

    # ------------------------------------------------------------------
    # 핸들러 — 시스템 / 유틸
    # ------------------------------------------------------------------

    def _handle_run(self, payload: dict) -> dict:
        """로컬 명령 실행 (OsBridge 위임).

        payload 키:
          cmd  실행 명령어 (화이트리스트)
          args 인자 리스트
          cwd  작업 디렉토리
        """
        cmd = payload.get("cmd", "")
        if not cmd:
            return {"error": "cmd 파라미터가 필요합니다"}
        return self._os.run(
            cmd,
            args=payload.get("args", []),
            cwd=payload.get("cwd"),
        )

    def _handle_speak(self, payload: dict) -> dict:
        """TTS 발화."""
        text = payload.get("text", "")
        if not text:
            return {"error": "text 파라미터가 필요합니다"}
        self._voice.speak(text)
        return {"spoken": text}

    def _handle_status(self, _payload: dict) -> dict:
        """scraper + backend 헬스 체크 및 응답 시간 측정."""
        results = {}
        services = [
            ("scraper", self._scraper_url, self._scraper_health_path),
            ("backend", self._backend_url, self._backend_health_path),
        ]
        for name, url, health_path in services:
            t0 = time.monotonic()
            try:
                resp = self._http.get(f"{url}{health_path}", timeout=5)
                elapsed_ms = round((time.monotonic() - t0) * 1000)
                if resp.status_code == 200:
                    results[name] = {"status": "ok", "latency_ms": elapsed_ms}
                else:
                    results[name] = {"status": f"HTTP {resp.status_code}", "latency_ms": elapsed_ms}
            except requests.ConnectionError:
                results[name] = {"status": "연결 실패", "latency_ms": -1}
            except requests.Timeout:
                results[name] = {"status": "타임아웃", "latency_ms": -1}
        return results

    def _handle_save(self, payload: dict) -> dict:
        """결과물을 output/reports/ 에 JSON으로 저장 (OsBridge 경유).

        payload 키:
          data      저장할 dict (없으면 _history 마지막 결과)
          filename  파일명 (확장자 제외)
        """
        data = payload.get("data") or (
            self._history[-1]["result"] if self._history else {}
        )
        filename = payload.get("filename", f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        path = f"../output/reports/{filename}.json"

        try:
            self._os.write_file(path, json.dumps(data, ensure_ascii=False, indent=2))
            return {"saved": path}
        except PermissionError as exc:
            return {"error": str(exc)}

    def _handle_history(self, payload: dict) -> dict:
        """최근 세션 히스토리 반환.

        payload 키:
          n  반환 건수 (기본 10)
        """
        n = int(payload.get("n", 10))
        recent = self._history[-n:]
        return {
            "total": len(self._history),
            "shown": len(recent),
            "records": [
                {
                    "seq":     r["seq"],
                    "time":    r["time"],
                    "command": r["command"],
                    "payload": r["payload"],
                    "elapsed_sec": r["elapsed_sec"],
                    "ok": "error" not in r["result"],
                }
                for r in recent
            ],
        }

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------

    def _record_history(self, command: str, payload: dict, result: Any, elapsed: float) -> None:
        entry = {
            "seq":         len(self._history) + 1,
            "time":        datetime.now().isoformat(timespec="seconds"),
            "command":     command,
            "payload":     payload,
            "result":      result,
            "elapsed_sec": elapsed,
        }
        self._history.append(entry)
        if len(self._history) > _MAX_HISTORY:
            self._history.pop(0)

    def _say(self, text: str) -> None:
        if self._voice_enabled:
            self._voice.speak(text)
        else:
            print(f"[JARVIS] {text}")

    def _listen_or_input(self, prompt: str) -> str:
        if self._voice_enabled and self._voice.available["stt"]:
            result = self._voice.listen()
            return result or ""
        return input(prompt)

    @staticmethod
    def _print_result(result: Any) -> None:
        if isinstance(result, dict) and "error" in result:
            print(f"  오류: {result['error']}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    @staticmethod
    def _print_help() -> None:
        print("""
┌─────────────────────────────────────────────────────┐
│  JARVIS 명령어 가이드                                │
├───────────────┬─────────────────────────────────────┤
│  자연어 입력  │  미디어아트 논문 찾아줘              │
│               │  인터랙티브 아트 보고서 만들어줘     │
│               │  서버 상태 확인해줘                  │
│               │  자동으로 검색하고 보고서 만들어줘   │
├───────────────┼─────────────────────────────────────┤
│  구조화 입력  │  search {"query":"미디어아트"}        │
│               │  report {"topic":"디지털 아트"}       │
│               │  pipeline {"query":"생성 AI 예술"}   │
│               │  status {}                           │
│               │  history {"n":5}                     │
│               │  save {"filename":"my_result"}        │
└───────────────┴─────────────────────────────────────┘
  종료: 'q', '종료', Ctrl+C
""")


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    JarvisAgent().run_interactive()
