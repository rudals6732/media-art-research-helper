# 미디어아트 논문 탐색기 & 보고서 작성 보조기

국내외 학술 데이터베이스(RISS, KCI)에서 논문을 수집하고, 수집된 자료를 기반으로 대학생·연구원 수준의 보고서 초안을 자동으로 구성하는 파이프라인입니다.

[![CI](https://github.com/rudals6732/media-art-research-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/rudals6732/media-art-research-helper/actions/workflows/ci.yml)

---

## 주요 기능

- **논문 검색** — RISS / KCI 크롤링 + OpenAPI 듀얼 지원, 중복 제거 및 할루시네이션 검증
- **텍스트 처리** — 초록 정제, 키워드 추출, 규칙 기반 패러프레이징
- **인용 생성** — APA / MLA / KCI 형식 자동 생성
- **보고서 초안** — 서론 / 본론 / 결론 / 참고문헌 자동 구성 (Java Spring Boot)
- **JARVIS 오케스트레이터** — 한국어 자연어 명령으로 전체 파이프라인 제어

---

## 프로젝트 구조

```
media-art-research-helper/
├── scrapper-python/        # Python 크롤러 & Flask API (포트 5000)
│   ├── src/
│   │   ├── crawler.py      # RISS / KCI 크롤러
│   │   ├── validator.py    # 출처 검증 & 중복 제거
│   │   └── text_processor.py  # 텍스트 정제 & 인용 생성
│   ├── tests/
│   ├── run.py              # Flask 서버 진입점
│   └── requirements.txt
├── backend-java/           # Spring Boot API 서버 (포트 8080)
│   └── src/main/java/com/project/
│       ├── controller/     # PaperController (REST 엔드포인트)
│       ├── service/        # ReportService, ScraperClient
│       └── model/          # Paper, ReportSection
├── jarvis-core/            # JARVIS 오케스트레이터
│   ├── src/
│   │   ├── jarvis_agent.py # 한국어 인텐트 파서 & 명령 디스패처
│   │   ├── os_bridge.py    # 로컬 명령 실행 (화이트리스트)
│   │   └── voice_handler.py   # STT / TTS (선택)
│   └── config.json
├── output/
│   ├── research_notes/     # 팩트 시트 (.txt)
│   └── reports/            # 최종 보고서 (.json, .md)
└── run_tests.ps1           # 통합 테스트 러너 (PowerShell)
```

---

## 시작하기

### 요구사항

| 도구 | 버전 |
|------|------|
| Python | 3.12+ |
| Java | 21+ |
| Maven | 3.9+ |

### Python 스크래퍼 설치 & 실행

```bash
cd scrapper-python
pip install -r requirements.txt

# KCI OpenAPI 키 설정 (선택 — 없으면 HTML 폴백)
cp .env.example .env
# .env 파일에 KCI_API_KEY=YOUR_KEY 입력

python run.py   # Flask 서버 실행 (localhost:5000)
```

### Java 백엔드 실행

```bash
cd backend-java
mvn spring-boot:run   # Spring Boot 서버 실행 (localhost:8080)
```

### JARVIS 오케스트레이터 실행

```bash
# Flask + Spring Boot 서버가 모두 실행 중인 상태에서
python -m jarvis-core.src.jarvis_agent
```

---

## API 엔드포인트

### Python 스크래퍼 (`:5000`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 확인 |
| POST | `/search` | 논문 검색 (RISS + KCI) |
| POST | `/cite` | 인용 문자열 생성 |

**검색 예시**
```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "미디어아트 인터랙티브", "limit": 10}'
```

### Java 백엔드 (`:8080`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/health` | 백엔드 + 스크래퍼 상태 확인 |
| POST | `/api/search` | 스크래퍼 검색 프록시 |
| POST | `/api/report` | 보고서 초안 생성 |

**보고서 생성 예시**
```bash
curl -X POST http://localhost:8080/api/report \
  -H "Content-Type: application/json" \
  -d '{"topic": "인터랙티브 미디어아트"}'
# papers 생략 시 스크래퍼에서 자동 검색
```

---

## JARVIS 명령어

```
JARVIS> 미디어아트 논문 찾아줘
JARVIS> 인터랙티브 아트 보고서 만들어줘
JARVIS> 자동으로 검색하고 보고서 만들어줘
JARVIS> 서버 상태 확인해줘

# 구조화된 입력도 지원
JARVIS> search {"query": "생성 AI 예술", "limit": 5}
JARVIS> pipeline {"query": "미디어아트"}
```

---

## 테스트

```powershell
# 통합 테스트 (환경 확인 + 파일 구조 + 컴파일 + 유닛 + 스모크 + Maven)
.\run_tests.ps1
```

```bash
# Python 유닛 테스트만
python -m unittest discover -s scrapper-python/tests -p "test_*.py" -v

# JARVIS 테스트만
python -m unittest jarvis-core/tests/test_intent_parser.py -v

# Java 테스트만
cd backend-java && mvn test
```

---

## 라이선스

MIT
