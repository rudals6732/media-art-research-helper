"""Flask API 서버 — Java 백엔드와 통신하는 Python 크롤러 엔드포인트."""
import logging
import os

from flask import Flask, request, jsonify

from src.crawler import search_all
from src.validator import filter_valid
from src.text_processor import process_abstract, generate_citation

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
app = Flask(__name__)


@app.get("/health")
def health():
    return "ok"


@app.post("/search")
def search():
    """논문 통합 검색 엔드포인트.

    Request body (JSON):
        query      : 검색어 (필수)
        limit      : 건수 (기본 10)
        check_url  : URL 접근성 검사 여부 (기본 true, 느림)
        dedup      : 중복 제거 여부 (기본 true)
        min_score  : 최소 통과 점수 0~100 (기본 60)

    Response: 검증·정제된 논문 리스트 (JSON)
    """
    body = request.get_json(force=True)
    query     = body.get("query", "").strip()
    limit     = int(body.get("limit", 10))
    check_url = bool(body.get("check_url", True))
    dedup     = bool(body.get("dedup", True))
    min_score = int(body.get("min_score", 60))

    if not query:
        return jsonify({"error": "query 파라미터가 필요합니다"}), 400

    papers = search_all(query, limit)
    papers = filter_valid(papers, check_url=check_url, dedup=dedup, min_score=min_score)

    for p in papers:
        if p.get("abstract"):
            p["processed"] = process_abstract(p["abstract"], paper=p)

    return jsonify(papers)


@app.post("/cite")
def cite():
    """단일 논문 인용 문자열 생성 엔드포인트.

    Request body (JSON):
        paper  : 논문 메타데이터 dict (필수)
        styles : 인용 형식 리스트 (기본 ["APA", "MLA", "KCI"])
    """
    body   = request.get_json(force=True)
    paper  = body.get("paper", {})
    styles = body.get("styles", ["APA", "MLA", "KCI"])

    if not paper:
        return jsonify({"error": "paper 파라미터가 필요합니다"}), 400

    citations = {s: generate_citation(paper, s) for s in styles}
    return jsonify(citations)


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
