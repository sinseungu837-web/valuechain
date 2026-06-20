"""
무료 뉴스 감성 분석 (LLM 없이, 키워드 기반).

네이버 뉴스(무료 API) 수십 건의 제목·요약을 모아
긍정/부정 키워드 출현으로 감성 점수를 낸다.

이것은 LLM이 아니라 '키워드 사전 기반 집계'다. 비용 0원.
종합 판단에서는 보조 신호로만 쓰고(가중치 작음),
객관적 재무·시계열 지표가 주력이다(verdict.py / app.py에서 가중합).
"""
from __future__ import annotations
from dataclasses import dataclass, field

# 주식 뉴스용 긍정/부정 키워드 사전 (한국어)
POS_WORDS = [
    "수주", "계약 체결", "공급계약", "납품", "최대 실적", "사상 최대", "호실적",
    "흑자전환", "흑자 전환", "흑자", "성장", "증가", "급등", "강세", "신고가",
    "수출 증가", "목표가 상향", "상향", "수혜", "호재", "어닝서프라이즈",
    "증설", "투자 확대", "신제품", "점유율 확대", "턴어라운드", "개선", "반등",
    "수요 증가", "체결", "선정", "승인", "허가", "돌파", "매수",
]
NEG_WORDS = [
    "적자전환", "적자 전환", "적자", "실적 부진", "부진", "급락", "약세",
    "하락", "목표가 하향", "하향", "감산", "리콜", "소송", "횡령", "배임",
    "유상증자", "감자", "악재", "손실", "부도", "위기", "우려", "감소",
    "공급 과잉", "수요 둔화", "둔화", "철수", "지연", "매도", "경고", "하회",
]


@dataclass
class NewsSentiment:
    count: int = 0            # 분석한 기사 수
    pos: int = 0             # 긍정 신호 출현 기사 수
    neg: int = 0             # 부정 신호 출현 기사 수
    score: float = 0.0       # -1 ~ +1 (긍정 우세 +)
    direction: str = "중립"   # 긍정우세 / 중립 / 부정우세
    pos_titles: list[str] = field(default_factory=list)
    neg_titles: list[str] = field(default_factory=list)


def _hits(text: str, words: list[str]) -> int:
    return sum(1 for w in words if w in text)


def analyze_news(company_name: str, display: int = 30) -> NewsSentiment:
    """
    종목명으로 뉴스 다수 수집 → 긍정/부정 키워드 집계.
    실패하면 빈 결과(중립).
    """
    try:
        from news.collector import search_news
        items = search_news(f"{company_name} 주가", display=display)
    except Exception:
        return NewsSentiment()

    if not items:
        return NewsSentiment()

    pos_titles, neg_titles = [], []
    pos_cnt = neg_cnt = 0
    for it in items:
        text = f"{it.title} {it.description}"
        p = _hits(text, POS_WORDS)
        n = _hits(text, NEG_WORDS)
        if p > n:
            pos_cnt += 1
            if len(pos_titles) < 5:
                pos_titles.append(it.title)
        elif n > p:
            neg_cnt += 1
            if len(neg_titles) < 5:
                neg_titles.append(it.title)

    total = len(items)
    # 감성 점수: (긍정-부정)/전체, -1~+1
    score = round((pos_cnt - neg_cnt) / total, 3) if total else 0.0
    if score >= 0.15:
        direction = "긍정우세"
    elif score <= -0.15:
        direction = "부정우세"
    else:
        direction = "중립"

    return NewsSentiment(
        count=total, pos=pos_cnt, neg=neg_cnt, score=score,
        direction=direction, pos_titles=pos_titles, neg_titles=neg_titles,
    )
