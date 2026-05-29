"""출처 교차 검증 — 할루시네이션(가짜 논문) 탐지 및 중복 제거 모듈.

검증 파이프라인
  1. 필드 무결성  : 제목·저자·연도 존재 여부 및 형식
  2. URL 접근성   : HEAD → GET 폴백으로 실재 확인
  3. 소스 URL 패턴: RISS/KCI URL 정규식 일치 검사
  4. 제목 유사도  : SequenceMatcher 기반 중복 논문 탐지
  5. 병렬 처리    : ThreadPoolExecutor로 I/O 대기 단축
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 소스별 URL 정규식 패턴
_SOURCE_URL_PATTERNS: dict[str, re.Pattern] = {
    "RISS": re.compile(r"https?://www\.riss\.kr/", re.I),
    "KCI":  re.compile(r"https?://www\.kci\.go\.kr/", re.I),
}

# 제목 쓰레기 탐지: 특수문자 비율 임계치
_GARBAGE_CHAR_RATIO = 0.35

# 중복 판정 유사도 임계치 (0~1, 높을수록 엄격)
_DUP_THRESHOLD = 0.85

# 저자 이름 정규식: 한글 2-5자 또는 영문 성,이름 형태
_AUTHOR_PATTERN = re.compile(
    r"[가-힣]{2,5}"           # 한글 이름
    r"|[A-Z][a-z]+,?\s[A-Z]"  # 영문 이름 (Kim, J / John Kim)
)


# ---------------------------------------------------------------------------
# 단일 논문 검증
# ---------------------------------------------------------------------------

def _check_title(title: str) -> list[str]:
    issues: list[str] = []
    if not title or len(title.strip()) < 4:
        issues.append("제목 너무 짧음")
        return issues

    non_alpha = sum(1 for c in title if not c.isalnum() and c not in " .,·-–()[]「」『』《》〈〉")
    if len(title) > 0 and non_alpha / len(title) > _GARBAGE_CHAR_RATIO:
        issues.append(f"제목 특수문자 과다({non_alpha}/{len(title)})")

    return issues


def _check_author(authors: str) -> list[str]:
    if not authors or not authors.strip():
        return ["저자 없음"]
    if not _AUTHOR_PATTERN.search(authors):
        return [f"저자 형식 불명확: {authors[:30]}"]
    return []


def _check_year(year) -> list[str]:
    try:
        y = int(year)
        if not (1900 < y < 2100):
            return [f"연도 범위 초과: {y}"]
    except (TypeError, ValueError):
        return ["연도 비정상"]
    return []


def _check_source_url(url: str, source: str) -> list[str]:
    if not url:
        return ["URL 없음"]
    pattern = _SOURCE_URL_PATTERNS.get(source)
    if pattern and not pattern.match(url):
        return [f"URL이 {source} 도메인과 불일치"]
    return []


def _check_url_reachable(url: str, timeout: int = 6) -> list[str]:
    if not url:
        return []
    try:
        # HEAD 먼저 시도 (빠름)
        resp = requests.head(url, timeout=timeout, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code < 400:
            return []
        # 일부 서버는 HEAD를 거부 → GET 재시도
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if resp.status_code < 400:
            return []
        return [f"URL {resp.status_code} 오류"]
    except requests.ConnectionError:
        return ["URL 연결 불가"]
    except requests.Timeout:
        return ["URL 타임아웃"]
    except requests.RequestException as exc:
        return [f"URL 접근 오류: {exc}"]


def verify_paper(paper: dict, check_url: bool = True) -> dict:
    """단일 논문 메타데이터 검증.

    반환 dict에 ``valid`` (bool), ``score`` (0~100), ``issues`` (list[str]) 추가.
    score: 필드 품질 점수 — URL 오류는 -20, 형식 오류는 -15 등으로 차감.
    """
    issues: list[str] = []

    issues += _check_title(paper.get("title", ""))
    issues += _check_author(paper.get("authors", ""))
    issues += _check_year(paper.get("year"))
    issues += _check_source_url(paper.get("url", ""), paper.get("source", ""))

    if check_url:
        issues += _check_url_reachable(paper.get("url", ""))

    score = max(0, 100 - len(issues) * 20)

    return {
        **paper,
        "valid": len(issues) == 0,
        "score": score,
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# 배치 검증 (병렬)
# ---------------------------------------------------------------------------

def validate_batch(
    papers: list[dict],
    check_url: bool = True,
    max_workers: int = 8,
) -> list[dict]:
    """논문 목록을 ThreadPoolExecutor로 병렬 검증."""
    results: list[dict] = [{}] * len(papers)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(verify_paper, p, check_url): i
            for i, p in enumerate(papers)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                logger.error("검증 예외 (index=%d): %s", idx, exc)
                results[idx] = {**papers[idx], "valid": False, "score": 0,
                                "issues": [f"검증 예외: {exc}"]}

    return results


# ---------------------------------------------------------------------------
# 중복 제거
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """비교용 제목 정규화: 소문자, 공백·특수문자 제거."""
    return re.sub(r"[\s\W]+", "", title.lower())


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def deduplicate(papers: list[dict], threshold: float = _DUP_THRESHOLD) -> list[dict]:
    """제목 유사도 기반 중복 논문 제거.

    score가 높은 쪽을 우선 보존. 동점이면 RISS > KCI 순.
    """
    source_priority = {"RISS": 0, "KCI": 1}
    sorted_papers = sorted(
        papers,
        key=lambda p: (-p.get("score", 0), source_priority.get(p.get("source", ""), 99)),
    )

    kept: list[dict] = []
    kept_titles: list[str] = []

    for paper in sorted_papers:
        norm = _normalize_title(paper.get("title", ""))
        if not norm:
            continue
        is_dup = any(_similarity(norm, t) >= threshold for t in kept_titles)
        if not is_dup:
            kept.append(paper)
            kept_titles.append(norm)

    logger.info("중복 제거: %d → %d건", len(papers), len(kept))
    return kept


# ---------------------------------------------------------------------------
# 통합 진입점
# ---------------------------------------------------------------------------

def filter_valid(
    papers: list[dict],
    check_url: bool = True,
    dedup: bool = True,
    min_score: int = 60,
) -> list[dict]:
    """검증 → 중복 제거 → score 임계치 필터 파이프라인.

    Args:
        papers:    크롤러에서 받은 원본 dict 리스트.
        check_url: URL 접근성 검사 포함 여부 (느림, 기본 True).
        dedup:     제목 유사도 중복 제거 여부.
        min_score: 최소 통과 점수 (0~100).
    """
    validated = validate_batch(papers, check_url=check_url)
    passed = [p for p in validated if p.get("score", 0) > min_score]

    if dedup:
        passed = deduplicate(passed)

    logger.info("filter_valid: %d → %d건 (min_score=%d)", len(papers), len(passed), min_score)
    return passed
