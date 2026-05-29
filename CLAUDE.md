# 프로젝트 가이드: 미디어아트 관련 논문 탐색기 및 보고서 작성 보조기

이 파일은 `Claude Code` 에이전트가 본 프로젝트의 아키텍처, 기술 스택, 코딩 컨벤션 및 개발 목적을 이해하고 준수하기 위한 공식 가이드라인이다.

## 1. 프로젝트 개요
- **목적**: 미디어아트 분야의 학술 논문, 전시 자료, 공공기관 보고서를 효율적으로 탐색하고, 이를 기반으로 대학생/연구원 수준의 보고서 작성을 보조하는 파이프라인 구축.
- **주요 기능**:
  1. 국내외 학술 데이터베이스(RISS, KCI, 과학기술정보통신부 등) 기반 논문 및 데이터 검색.
  2. 수집된 자료의 패러프레이징(교정) 및 표절 방지용 원문 변형 엔진 운영.
  3. 보고서 초안(서론, 본론, 결론, 진짜 참고문헌) 자동 구성 및 포맷팅 보조.

---

## 2. 프로젝트 구조 (Project Structure)
```text
media-art-research-helper/
│
├── claude.md                   # 본 가이드 파일
├── README.md                   # 프로젝트 구동 및 실행 안내
│
├── backend-java/               # Java 기반 데이터 처리 및 백엔드 서버
│   ├── src/main/java/com/project/
│   │   ├── controller/         # API 엔드포인트
│   │   ├── service/            # 보고서 구조 생성 및 비즈니스 로직
│   │   └── model/              # 데이터 구조 (논문 정보, 보고서 섹션 등)
│   └── pom.xml (or build.gradle)
│
├── scrapper-python/            # Python3 기반 학술 자료 및 URL 크롤링 엔진
│   ├── src/
│   │   ├── crawler.py          # RISS, KCI, 공공기관 데이터 스크래핑
│   │   ├── validator.py        # 할루시네이션(가짜 출처) 교차 검증 모듈
│   │   └── text_processor.py   # 텍스트 추출 및 패러프레이징 전처리
│   ├── requirements.txt
│   └── run.py
│
└── output/                     # 생성된 보고서 및 리서치 자료 저장소
    ├── research_notes/         # 팩트 시트 텍스트 파일 (.txt)
    └── reports/                # 최종 완성본 파일 아카이브 (.md, .docx)
```

---

## 6. 자비스 오케스트레이터 지침 (JARVIS Orchestrator Guidelines)
- **개념**: 프로젝트 전체(Python 크롤러, Java 백엔드, 문서 자동화)를 총괄 제어하고 사용자의 시스템 명령을 자율 수행하는 AI 비서 시스템 모듈.
- **구조 추가**:
```text
media-art-research-helper/
└── jarvis-core/                # 자비스 자율 제어 및 오케스트레이션 모듈
    ├── src/
    │   ├── jarvis_agent.py     # 시스템 명령어 해석 및 워크플로우 통제 컨트롤러
    │   ├── voice_handler.py    # (선택) STT/TTS 음성 인터페이스 처리
    │   └── os_bridge.py        # 로컬 파일 시스템 및 터미널 자동 실행 브릿지
    └── config.json
```
