"""
뉴스 기사 수 + 최신성으로 "지금 뜨는 섹터" 자동 감지.

섹터별로 대표 검색어 묶음을 정의하고,
각 묶음의 최근 기사 수를 합산해 섹터 열기(heat) 점수를 만든다.
"""
from __future__ import annotations
from dataclasses import dataclass
from news.collector import search_news_with_total


# 섹터별 검색어 묶음 (기사 수가 많을수록 뜨거운 섹터)
SECTOR_QUERIES: dict[str, list[str]] = {
    "반도체":  ["반도체 수출", "HBM 수주", "반도체 장비", "파운드리"],
    "AI/전력": ["AI 데이터센터", "전력 인프라", "변압기 수주", "AI 서버"],
    "배터리":  ["배터리 수주", "전기차 배터리", "양극재", "배터리 소재"],
    "방산":    ["방산 수출", "K방산", "무기 수주", "방위산업"],
    "바이오":  ["바이오 임상", "신약 허가", "바이오텍", "제약 수출"],
    "조선":    ["조선 수주", "LNG선", "HD현대", "삼성중공업"],
    "2차전지": ["2차전지", "리튬 배터리", "전고체 배터리", "배터리 팩"],
}


@dataclass
class SectorHeat:
    sector: str
    heat: int          # 총 기사 수 (높을수록 핫함)
    top_headlines: list[str]   # 대표 헤드라인 3개


def detect_hot_sectors(top_n: int = 3) -> list[SectorHeat]:
    """
    뉴스 기사 수 기준으로 가장 뜨거운 섹터 top_n개 반환.
    각 섹터당 쿼리 묶음을 검색하고 기사 수를 합산.
    """
    print("섹터 열기 측정 중 (네이버 뉴스)...")
    results: list[SectorHeat] = []

    for sector, queries in SECTOR_QUERIES.items():
        total = 0
        headlines: list[str] = []
        for q in queries:
            try:
                items, cnt = search_news_with_total(q, display=3)
                total += cnt
                for it in items[:2]:
                    if it.title and it.title not in headlines:
                        headlines.append(it.title)
            except Exception as e:
                print(f"  [경고] '{q}' 검색 실패: {e}")

        results.append(SectorHeat(
            sector=sector,
            heat=total,
            top_headlines=headlines[:3],
        ))
        print(f"  {sector:8s}: 기사 {total}건")

    results.sort(key=lambda x: x.heat, reverse=True)
    return results[:top_n]
