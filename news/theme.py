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
    # 기존
    "반도체":    ["반도체 수출", "HBM 수주", "반도체 장비", "파운드리"],
    "AI/전력":   ["AI 데이터센터", "전력 인프라", "변압기 수주", "AI 서버"],
    "배터리":    ["배터리 수주", "전기차 배터리", "양극재", "배터리 소재"],
    "방산":      ["방산 수출", "K방산", "무기 수주", "방위산업"],
    "바이오":    ["바이오 임상", "신약 허가", "바이오텍", "제약 수출"],
    "조선":      ["조선 수주", "LNG선", "HD현대", "삼성중공업"],
    "2차전지":   ["2차전지", "리튬 배터리", "전고체 배터리", "배터리 팩"],
    "로봇":      ["로봇 수주", "협동로봇", "피지컬AI 로봇", "산업용 로봇"],
    "우주항공":  ["우주 발사체", "위성 수주", "누리호", "우주항공청"],
    # 신규
    "자동차":    ["자동차 수출", "현대차 실적", "기아 수주", "완성차"],
    "온라인쇼핑":["이커머스 성장", "네이버쇼핑", "온라인쇼핑 매출", "쿠팡"],
    "외식/식품": ["외식 매출", "식품 수출", "프랜차이즈 확장", "K푸드"],
    "생활소비재":["화장품 수출", "K뷰티", "생활용품 매출", "아모레"],
    "의료기기":  ["의료기기 수출", "임플란트 수주", "진단키트", "의료AI"],
    "유통":      ["유통 매출", "백화점 실적", "편의점 성장", "이마트"],
    "온라인게임":["게임 출시", "신작 매출", "게임 수출", "크래프톤"],
    "증권/금융": ["증권사 실적", "IPO 시장", "금리 인하", "자산운용"],
    "지주사":    ["지주사 배당", "자회사 실적", "지배구조 개선", "SK CJ"],
    "무역":      ["수출 실적", "원자재 수급", "무역흑자", "상사 수주"],
    "반도체소재":["반도체 소재 국산화", "식각액 수주", "특수가스", "포토레지스트"],
    "파운드리":  ["파운드리 수주", "TSMC 경쟁", "삼성 파운드리", "8인치"],
    "팹리스":    ["팹리스 설계", "AI반도체 설계", "SoC 개발", "칩 수주"],
    "종합반도체":["IDM 전략", "HBM 양산", "D램 수요", "반도체 투자"],
    "전기설비":  ["변압기 수출", "전력설비 수주", "LS일렉트릭", "전기인프라"],
    "철강":      ["철강 가격", "포스코 실적", "철근 수요", "고로 감산"],
    "전자부품":  ["MLCC 수주", "카메라모듈 납품", "PCB 수요", "삼성전기"],
    "전기차":    ["전기차 판매", "배터리 수주", "충전 인프라", "EV 수요"],
    "건설":      ["아파트 분양", "해외건설 수주", "건설 착공", "주택경기"],
}


# 경기방어/안정 성격 섹터 (소비·필수재·금융 등 — 뉴스 변동성 작고 꾸준)
DEFENSIVE_SECTORS = {
    "생활소비재", "유통", "외식/식품", "의료기기",
    "증권/금융", "지주사", "자동차", "철강",
}


@dataclass
class SectorHeat:
    sector: str
    heat: int          # 총 기사 수 (높을수록 핫함)
    top_headlines: list[str]   # 대표 헤드라인 3개


def _measure_all_sectors() -> list[SectorHeat]:
    """전체 섹터의 뉴스 열기를 측정해 heat 내림차순 정렬 반환."""
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
    return results


def detect_hot_sectors(top_n: int = 3) -> list[SectorHeat]:
    """뉴스 기사 수 기준 가장 뜨거운 섹터 top_n개."""
    return _measure_all_sectors()[:top_n]


def detect_hot_and_stable(hot_n: int = 5, stable_n: int = 5
                          ) -> tuple[list[SectorHeat], list[SectorHeat]]:
    """
    핫한 섹터 hot_n개 + 안정(경기방어) 섹터 stable_n개를 나눠서 반환.

    - 핫: 전체 섹터 중 뉴스 기사 수 상위 (시장이 지금 주목)
    - 안정: DEFENSIVE_SECTORS(소비·필수재·금융 등) 중 뉴스 열기 순
            → 경기 영향이 적고 꾸준한 수요가 있는 방어적 섹터
    핫에 이미 포함된 섹터는 안정 목록에서 제외(중복 방지).
    """
    ranked = _measure_all_sectors()
    hot = ranked[:hot_n]
    hot_names = {s.sector for s in hot}

    stable = [s for s in ranked
              if s.sector in DEFENSIVE_SECTORS and s.sector not in hot_names]
    return hot, stable[:stable_n]
