"""RISS, KCI 학술 데이터베이스 크롤러.

RISS: requests + BeautifulSoup (쿠키 워밍 → 검색 → HTML 파싱)
KCI : OpenAPI 우선(KCI_API_KEY 환경변수), 키 없으면 HTML 폴백
"""

import hashlib
import logging
import os
import random
import time
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class PaperMeta:
    id: str
    title: str
    authors: str
    journal: str
    year: int
    abstract: str
    url: str
    source: str


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _get(
    session: requests.Session,
    url: str,
    params: dict | None = None,
    retries: int = 3,
    base_delay: float = 1.5,
) -> Optional[requests.Response]:
    """재시도 포함 GET 요청. 실패 시 None 반환."""
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=12)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning("[%d/%d] GET %s → %s", attempt + 1, retries, url, exc)
            if attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1) + random.uniform(0.0, 0.5))
    return None


def _paper_id(source: str, key: str) -> str:
    return f"{source}_{hashlib.md5(key.encode()).hexdigest()[:8]}"


def _extract_year(text: str) -> int:
    """문자열에서 4자리 연도(1900~2100)를 추출."""
    digits = "".join(filter(str.isdigit, text))
    for i in range(len(digits) - 3):
        y = int(digits[i : i + 4])
        if 1900 < y < 2100:
            return y
    return 0


# ---------------------------------------------------------------------------
# RISS 크롤러
# ---------------------------------------------------------------------------

class RissCrawler:
    """RISS 국내학술자료 검색 크롤러."""

    _HOME = "https://www.riss.kr"
    _SEARCH = "https://www.riss.kr/search/Search.do"

    def __init__(self):
        self.session = _session()
        # 쿠키 세팅을 위한 홈 페이지 선방문
        try:
            self.session.get(self._HOME, timeout=10)
        except requests.RequestException as exc:
            logger.debug("RISS 홈 접근 실패(무시): %s", exc)

    def search(self, query: str, limit: int = 10) -> list[PaperMeta]:
        params = {
            "isDetailSearch": "N",
            "searchGubun": "true",
            "viewYn": "OP",
            "query": query,
            "gu": "DETAIL",
            "order": "/DESC",
            "orderField": "RANK",
            "loadPageIndex": "1",
            "resultsView": str(min(limit, 20)),
            "iGroupView": "5",
            "ms": "1",
            "multilang": "0",
        }
        resp = _get(self.session, self._SEARCH, params=params)
        if resp is None:
            logger.error("RISS 검색 응답 없음 (query=%s)", query)
            return []

        results = self._parse(resp.text, limit)
        logger.info("RISS: %d건 수집 (query=%s)", len(results), query)
        return results

    def _parse(self, html: str, limit: int) -> list[PaperMeta]:
        soup = BeautifulSoup(html, "lxml")
        papers: list[PaperMeta] = []

        # RISS 결과 목록 — DOM이 배포판마다 달라질 수 있으므로 후보 선택자를 순서대로 시도
        items = (
            soup.select("ul.srchResultListW > li.item")
            or soup.select(".result_list > li")
            or soup.select("#searchListForm li")
        )

        for item in items[:limit]:
            try:
                paper = self._parse_item(item)
                if paper:
                    papers.append(paper)
            except Exception as exc:
                logger.debug("RISS 항목 파싱 오류: %s", exc)

        return papers

    def _parse_item(self, item) -> Optional[PaperMeta]:
        # 제목 + URL
        title_tag = (
            item.select_one("p.title a")
            or item.select_one(".title a")
            or item.select_one("a.tit")
        )
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = urljoin(self._HOME, href) if href else ""

        # 메타(저자 | 학술지 | 연도)
        meta_tag = item.select_one(".etc_box") or item.select_one(".srch_sub")
        meta_parts = (
            [p.strip() for p in meta_tag.get_text(" | ", strip=True).split("|")]
            if meta_tag else []
        )
        authors = meta_parts[0] if len(meta_parts) > 0 else ""
        journal = meta_parts[1] if len(meta_parts) > 1 else ""
        year = 0
        for part in reversed(meta_parts):
            y = _extract_year(part)
            if y:
                year = y
                break

        # 초록
        abstract_tag = (
            item.select_one(".preAbstract")
            or item.select_one(".abstract")
            or item.select_one(".cont")
        )
        abstract = abstract_tag.get_text(strip=True) if abstract_tag else ""

        return PaperMeta(
            id=_paper_id("RISS", url or title),
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            url=url,
            source="RISS",
        )


# ---------------------------------------------------------------------------
# KCI 크롤러
# ---------------------------------------------------------------------------

class KciCrawler:
    """KCI(한국학술지인용색인) 크롤러.

    KCI_API_KEY 환경변수가 있으면 OpenAPI를 호출하고,
    없으면 HTML 검색 페이지를 파싱한다.
    """

    _API = "https://www.kci.go.kr/kciportal/openapi/articleSearch.kci"
    _SEARCH = "https://www.kci.go.kr/kciportal/po/search/poSearchArticleList.kci"
    _BASE = "https://www.kci.go.kr"

    def __init__(self):
        self.api_key = os.getenv("KCI_API_KEY", "")
        self.session = _session()

    def search(self, query: str, limit: int = 10) -> list[PaperMeta]:
        if self.api_key:
            results = self._search_api(query, limit)
            if results:
                logger.info("KCI API: %d건 수집 (query=%s)", len(results), query)
                return results
            logger.warning("KCI API 결과 없음, HTML 폴백 시도")
        return self._search_html(query, limit)

    # ------------------------------------------------------------------
    # OpenAPI 경로
    # ------------------------------------------------------------------

    def _search_api(self, query: str, limit: int) -> list[PaperMeta]:
        params = {
            "apiKey": self.api_key,
            "title": query,
            "displayCount": min(limit, 100),
            "startIndex": 1,
        }
        resp = _get(self.session, self._API, params=params)
        if resp is None:
            return []
        try:
            soup = BeautifulSoup(resp.text, "lxml-xml")
            records = soup.find_all("record") or soup.find_all("item")
            return [self._api_record_to_paper(r) for r in records[:limit] if r]
        except Exception as exc:
            logger.warning("KCI API XML 파싱 오류: %s", exc)
            return []

    @staticmethod
    def _api_record_to_paper(record) -> PaperMeta:
        def txt(tag: str) -> str:
            el = record.find(tag)
            return el.get_text(strip=True) if el else ""

        url = txt("articleLink") or txt("url") or txt("link")
        year_raw = txt("publishYear") or txt("year") or txt("pubYear")
        year = _extract_year(year_raw)

        return PaperMeta(
            id=_paper_id("KCI", url or txt("title")),
            title=txt("title") or txt("articleTitle"),
            authors=txt("author") or txt("authors") or txt("writer"),
            journal=txt("journalName") or txt("journal") or txt("source"),
            year=year,
            abstract=txt("abstract") or txt("summary"),
            url=url,
            source="KCI",
        )

    # ------------------------------------------------------------------
    # HTML 폴백 경로
    # ------------------------------------------------------------------

    def _search_html(self, query: str, limit: int) -> list[PaperMeta]:
        params = {
            "menuId": "m01060200",
            "searchWhere": "all",
            "searchWord": query,
            "pageSize": min(limit, 10),
        }
        resp = _get(self.session, self._SEARCH, params=params)
        if resp is None:
            logger.error("KCI HTML 검색 응답 없음 (query=%s)", query)
            return []

        results = self._parse_html(resp.text, limit)
        logger.info("KCI HTML: %d건 수집 (query=%s)", len(results), query)
        return results

    def _parse_html(self, html: str, limit: int) -> list[PaperMeta]:
        soup = BeautifulSoup(html, "lxml")
        papers: list[PaperMeta] = []

        items = (
            soup.select(".article-list li")
            or soup.select(".searchResult li")
            or soup.select("#searchList li")
        )

        for item in items[:limit]:
            try:
                paper = self._parse_html_item(item)
                if paper:
                    papers.append(paper)
            except Exception as exc:
                logger.debug("KCI 항목 파싱 오류: %s", exc)

        return papers

    def _parse_html_item(self, item) -> Optional[PaperMeta]:
        title_tag = (
            item.select_one(".title a")
            or item.select_one("a.tit")
            or item.select_one(".articleTitle a")
        )
        if not title_tag:
            return None

        title = title_tag.get_text(strip=True)
        href = title_tag.get("href", "")
        url = urljoin(self._BASE, href) if href else ""

        def _text(selector: str) -> str:
            tag = item.select_one(selector)
            return tag.get_text(strip=True) if tag else ""

        authors = _text(".author") or _text(".writers") or _text(".creator")
        journal = _text(".journal") or _text(".journalName") or _text(".source")
        year_raw = _text(".year") or _text(".pub-year") or _text(".pubYear")
        year = _extract_year(year_raw)
        abstract = _text(".abstract") or _text(".summary") or _text(".preAbstract")

        return PaperMeta(
            id=_paper_id("KCI", url or title),
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract=abstract,
            url=url,
            source="KCI",
        )


# ---------------------------------------------------------------------------
# 통합 진입점
# ---------------------------------------------------------------------------

def search_all(query: str, limit: int = 10) -> list[dict]:
    """RISS + KCI 통합 검색.

    각 소스에서 최대 limit건씩 수집한 뒤 ID 기준으로 중복을 제거하여 반환.
    소스 간에는 서버 부하 방지용 지연(1~2초)을 삽입.
    """
    crawlers = [RissCrawler(), KciCrawler()]
    seen: set[str] = set()
    results: list[dict] = []

    for crawler in crawlers:
        try:
            papers = crawler.search(query, limit)
            for p in papers:
                d = asdict(p)
                if d["id"] not in seen:
                    seen.add(d["id"])
                    results.append(d)
        except Exception as exc:
            logger.error("%s 실패: %s", type(crawler).__name__, exc)
        finally:
            time.sleep(random.uniform(1.0, 2.0))

    return results
