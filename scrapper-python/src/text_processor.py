"""텍스트 추출, 키워드 분석, 패러프레이징, 인용 포맷 생성 모듈.

파이프라인
  clean_text      → HTML·특수문자 정제
  extract_sentences → 한국어 인식 문장 분리
  extract_keywords  → 불용어 제거 후 TF 기반 키워드 추출
  paraphrase        → 동의어 치환 + 어미·접속사 변환 (규칙 기반)
  generate_citation → APA / MLA / KCI 인용 형식 생성
  process_abstract  → 위 기능을 묶은 단일 진입점
"""

import html
import re
from collections import Counter
from typing import Literal

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 한국어 불용어 (조사·어미·관사류 포함)
_STOPWORDS: frozenset[str] = frozenset({
    "이", "그", "저", "것", "수", "등", "및", "에", "을", "를", "이", "가",
    "은", "는", "의", "로", "으로", "와", "과", "에서", "에게", "도", "만",
    "하다", "있다", "되다", "하여", "하고", "으며", "이며", "이고", "에서",
    "통해", "위해", "대한", "관한", "따른", "기반", "중심", "중", "내",
    "본", "각", "해당", "다양", "전반", "전체", "모든", "이러한", "그러한",
    "때", "때문", "경우", "통하여", "따라서", "또한", "하지만", "그러나",
    "더불어", "아울러", "특히", "주로", "실제", "이후", "이전", "현재",
    "최근", "일반", "가장", "매우", "더욱", "그러므로", "따라",
    # 영문
    "the", "a", "an", "of", "in", "to", "and", "is", "are", "was",
    "were", "for", "on", "with", "this", "that", "by", "from", "as",
    "be", "it", "or", "at", "has", "have", "been", "which", "their",
    "its", "not", "but", "also", "can", "will", "more", "than",
})

# 동의어 치환 테이블 {원어: [대체어, ...]}
_SYNONYMS: dict[str, list[str]] = {
    # 동사/형용사
    "연구하다": ["고찰하다", "탐구하다", "조사하다"],
    "분석하다": ["검토하다", "파악하다", "해석하다"],
    "제안하다": ["제시하다", "제언하다", "권고하다"],
    "활용하다": ["이용하다", "적용하다", "응용하다"],
    "개발하다": ["구현하다", "설계하다", "구축하다"],
    "나타났다": ["드러났다", "밝혀졌다", "확인됐다"],
    "보여준다": ["나타낸다", "드러낸다", "제시한다"],
    # 명사
    "연구":   ["고찰", "탐구", "조사"],
    "분석":   ["검토", "파악", "해석"],
    "방법":   ["방식", "기법", "접근법"],
    "결과":   ["성과", "산출", "도출"],
    "기술":   ["기법", "방법론", "테크놀로지"],
    "시스템": ["체계", "플랫폼", "구조"],
    "효과":   ["영향", "성과", "효율"],
    "목적":   ["목표", "취지", "의도"],
    "중요성": ["중요도", "의의", "의미"],
    "특성":   ["특징", "속성", "특질"],
    "과정":   ["절차", "프로세스", "단계"],
    "사례":   ["예시", "경우", "실례"],
    "연구자": ["학자", "연구원", "연구진"],
    # 접속사·부사
    "또한":   ["아울러", "더불어", "이와 함께"],
    "그러나": ["하지만", "반면에", "이와 달리"],
    "따라서": ["이에 따라", "그러므로", "이러한 이유로"],
    "특히":   ["특별히", "무엇보다", "특히"],
    # 미디어아트 전문 용어
    "미디어아트":  ["미디어 예술", "미디어 기반 예술"],
    "인터랙티브":  ["상호작용적", "인터랙션 기반"],
    "디지털 기술": ["디지털 매체 기술", "전자 기반 기술"],
    # 어미 변환 (단어 단위 치환으로 처리)
    "있다":   ["존재한다", "나타난다"],
    "한다":   ["이루어진다", "수행된다"],
    "된다":   ["이루어진다", "진행된다"],
}

# 어미 변환 패턴 {정규식: 대체 함수 or 문자열}
_ENDING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"되었다"), "이루어졌다"),
    (re.compile(r"하였다"), "수행하였다"),
    (re.compile(r"하고 있다"), "진행하고 있다"),
    (re.compile(r"알 수 있다"), "파악할 수 있다"),
    (re.compile(r"볼 수 있다"), "확인할 수 있다"),
    (re.compile(r"나타난다"), "드러난다"),
    (re.compile(r"중요하다"), "핵심적이다"),
]

# 인용 형식 타입
CitationStyle = Literal["APA", "MLA", "KCI"]


# ---------------------------------------------------------------------------
# 1. 텍스트 정제
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """HTML 엔티티 디코딩 → 태그 제거 → 공백 정규화."""
    text = html.unescape(text)                      # &amp; → &, &lt; → < 등
    text = re.sub(r"<[^>]+>", "", text)             # HTML 태그 제거
    text = re.sub(r"\[.*?\]|\(.*?\)", " ", text)    # 괄호 내 참조 번호 제거
    text = re.sub(r"[^\w\s.,!?·。；：%\-–()「」]", " ", text)  # 잡문자 제거
    text = re.sub(r"[ \t]+", " ", text)             # 수평 공백 정규화
    text = re.sub(r"\n{2,}", "\n", text)            # 연속 줄바꿈 축소
    return text.strip()


# ---------------------------------------------------------------------------
# 2. 문장 분리
# ---------------------------------------------------------------------------

# 한국어 마침표·영문 마침표·문장 종결 부호
_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?。])\s+"           # 영문 종결
    r"|(?<=[다])\s+"             # 한국어 어미 '다'
    r"|(?<=[임])\s+"             # 한국어 어미 '임'
    r"|(?<=[음])\s+"             # 한국어 어미 '음'
)


def extract_sentences(text: str) -> list[str]:
    """한국어/영문 혼재 텍스트에서 문장 단위로 분리."""
    cleaned = clean_text(text)
    raw = _SENTENCE_BOUNDARY.split(cleaned)
    return [s.strip() for s in raw if len(s.strip()) > 8]


# ---------------------------------------------------------------------------
# 3. 키워드 추출
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z]{3,}")


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """불용어 제거 후 단순 빈도(TF) 기반 키워드 추출."""
    tokens = _TOKEN.findall(clean_text(text))
    filtered = [t for t in tokens if t.lower() not in _STOPWORDS and len(t) > 1]
    freq = Counter(filtered)
    return [word for word, _ in freq.most_common(top_n)]


# ---------------------------------------------------------------------------
# 4. 패러프레이징 (규칙 기반)
# ---------------------------------------------------------------------------

def _apply_synonyms(text: str) -> str:
    """동의어 테이블을 긴 키 우선으로 적용."""
    for original, alternatives in sorted(_SYNONYMS.items(), key=lambda x: -len(x[0])):
        if original in text:
            # 동의어 중 첫 번째 선택 (결정적 동작)
            text = text.replace(original, alternatives[0], 1)
    return text


def _apply_ending_variants(text: str) -> str:
    """어미·서술어 패턴을 변환."""
    for pattern, replacement in _ENDING_PATTERNS:
        text = pattern.sub(replacement, text, count=1)
    return text


def _reorder_clauses(sentence: str) -> str:
    """'A하여 B한다' 형태를 'B하는 데 A를 활용한다'로 변환 (한정적 적용)."""
    match = re.match(r"^(.+?하여)\s+(.+한다)$", sentence)
    if match:
        clause_a, clause_b = match.group(1), match.group(2)
        return f"{clause_b}는 데 {clause_a} 활용한다"
    return sentence


def paraphrase(text: str) -> str:
    """규칙 기반 패러프레이징.

    동의어 치환 → 어미 변환 → 절 재구성 순서로 적용.
    Claude API 연동 시 이 함수를 대체할 것.
    """
    result = _apply_synonyms(text)
    sentences = extract_sentences(result)
    transformed = []
    for sent in sentences:
        sent = _apply_ending_variants(sent)
        sent = _reorder_clauses(sent)
        transformed.append(sent)
    return " ".join(transformed) if transformed else result


# ---------------------------------------------------------------------------
# 5. 인용 형식 생성
# ---------------------------------------------------------------------------

def generate_citation(paper: dict, style: CitationStyle = "APA") -> str:
    """논문 메타데이터로 참고문헌 인용 문자열 생성.

    지원 형식:
      APA  : Author, A. (Year). Title. *Journal*.
      MLA  : Author. "Title." *Journal*, Year.
      KCI  : 저자 (연도). 제목. 학술지명.
    """
    title   = paper.get("title", "제목 없음")
    authors = paper.get("authors", "저자 미상")
    journal = paper.get("journal", "학술지 미상")
    year    = paper.get("year", "연도 미상")
    url     = paper.get("url", "")
    url_str = f" Retrieved from {url}" if url else ""

    if style == "APA":
        return f"{authors} ({year}). {title}. *{journal}*.{url_str}"
    elif style == "MLA":
        return f'{authors}. "{title}." *{journal}*, {year}.{url_str}'
    elif style == "KCI":
        return f"{authors} ({year}). {title}. {journal}."
    else:
        raise ValueError(f"지원하지 않는 인용 형식: {style}")


# ---------------------------------------------------------------------------
# 6. 텍스트 통계
# ---------------------------------------------------------------------------

def text_stats(text: str) -> dict:
    """문자 수, 어절 수, 문장 수를 반환."""
    cleaned = clean_text(text)
    words = cleaned.split()
    sentences = extract_sentences(cleaned)
    return {
        "char_count": len(cleaned),
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_sentence_length": round(len(words) / len(sentences), 1) if sentences else 0,
    }


# ---------------------------------------------------------------------------
# 7. 통합 진입점
# ---------------------------------------------------------------------------

def process_abstract(abstract: str, paper: dict | None = None) -> dict:
    """초록 전처리 파이프라인 — 단일 진입점.

    Args:
        abstract: 원문 초록 텍스트.
        paper:    논문 메타데이터 dict (인용 생성에 사용, 없으면 인용 생략).

    Returns:
        cleaned       : 정제된 텍스트
        sentences     : 문장 리스트
        keywords      : 키워드 top-10
        paraphrased   : 패러프레이즈 결과
        stats         : 텍스트 통계
        citations     : APA/MLA/KCI 인용 문자열 (paper 전달 시에만)
    """
    cleaned = clean_text(abstract)
    result: dict = {
        "cleaned":    cleaned,
        "sentences":  extract_sentences(cleaned),
        "keywords":   extract_keywords(cleaned),
        "paraphrased": paraphrase(cleaned),
        "stats":      text_stats(cleaned),
    }

    if paper:
        result["citations"] = {
            style: generate_citation(paper, style)  # type: ignore[arg-type]
            for style in ("APA", "MLA", "KCI")
        }

    return result
