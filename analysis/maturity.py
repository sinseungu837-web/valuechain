"""
성숙도 분류기 (Maturity Classifier).

곡괭이 점수(구조+실적)와 별개로,
'시장이 이미 이 종목을 알아봤는가'를 측정해서 종목을 나눈다.

두 축:
    X축 = shovel_score   : 곡괭이 구조+실적이 좋은가 (이미 shovel.py에서 계산)
    Y축 = market_recognition : 시장이 이미 값을 매겼는가

market_recognition 측정 신호 (객관적 데이터만):
    - valuation     : PER/PBR이 높은가 (높을수록 이미 기대가 반영됨)
    - price_run      : 최근 주가가 많이 올랐는가 (이미 달린 종목)
    - size           : 시총이 큰가 (이미 대형주면 알려진 것)

4분면:
    ┌─────────────────────┬─────────────────────┐
    │ ② 검증된 성장주        │ ① 핵심 곡괭이(이미 비쌈) │  ← 시장이 앎(고평가)
    │ 곡괭이 약함+이미 비쌈   │ 곡괭이 강함+이미 비쌈    │
    ├─────────────────────┼─────────────────────┤
    │ ④ 함정/관심밖          │ ③ 숨은 곡괭이 ★        │  ← 시장이 모름(저평가)
    │ 곡괭이 약함+저평가      │ 곡괭이 강함+저평가      │
    └─────────────────────┴─────────────────────┘
       곡괭이 약함              곡괭이 강함

    ① = 이미 유명해지고 주가도 오른 곡괭이 (안전하지만 상승여력 제한)
    ③ = 같은 곡괭이 구조인데 아직 시장이 안 알아본 저가주 ★우리가 찾는 보석
    ④ = 곡괭이도 아니고 싼 것 = 그냥 싼 데는 이유가 있음 (대부분 피해야)
"""
from __future__ import annotations
from dataclasses import dataclass
from analysis.shovel import ShovelScore


@dataclass
class MarketSignals:
    """시장 인식도 측정용 데이터."""
    code: str
    per: float | None        # 주가수익비율
    pbr: float | None        # 주가순자산비율
    price_return_1y: float   # 최근 1년 주가 수익률 (%)
    market_cap: float        # 시가총액 (원)


@dataclass
class Classified:
    code: str
    name: str
    shovel_score: float       # 곡괭이 점수 (구조+실적)
    recognition: float        # 시장 인식도 0~1 (높을수록 이미 알려짐)
    quadrant: str             # '핵심곡괭이' | '숨은곡괭이' | '검증된성장주' | '관심밖'
    label: str                # 사람이 읽는 한 줄 설명


class MaturityClassifier:
    # 업종 평균 PER 기준 (반도체 장비주 기준값, 산업별로 조정 가능)
    SECTOR_AVG_PER = 20.0
    SECTOR_AVG_PBR = 3.0

    def recognition(self, sig: MarketSignals) -> float:
        """
        시장 인식도 0~1. 높을수록 '이미 비싸고 알려진' 종목.
        밸류에이션 + 주가상승 + 규모를 합산.
        """
        score = 0.0

        # 밸류에이션: 업종평균 대비 높으면 이미 기대가 반영된 것
        if sig.per and sig.per > 0:
            score += min(1.0, sig.per / self.SECTOR_AVG_PER) * 0.40
        if sig.pbr and sig.pbr > 0:
            score += min(1.0, sig.pbr / self.SECTOR_AVG_PBR) * 0.25

        # 주가 상승: 이미 많이 오른 종목은 시장이 알아본 것
        score += min(1.0, max(0, sig.price_return_1y) / 100.0) * 0.25  # 1년 100%면 만점

        # 규모: 시총 5조 이상이면 충분히 알려진 대형주로 봄
        score += min(1.0, sig.market_cap / 5e12) * 0.10

        return round(min(1.0, score), 3)

    def classify(self, shovel: ShovelScore, sig: MarketSignals,
                 shovel_threshold: float = 0.5,
                 recog_threshold: float = 0.55) -> Classified:
        recog = self.recognition(sig)
        strong_shovel = shovel.total >= shovel_threshold
        well_known = recog >= recog_threshold

        if strong_shovel and well_known:
            q, label = "핵심곡괭이", "이미 시장이 알아본 검증된 곡괭이 -안전하나 상승여력 제한"
        elif strong_shovel and not well_known:
            q, label = "숨은곡괭이", "★ 같은 곡괭이 구조인데 아직 저평가 -재평가 여력 큼"
        elif not strong_shovel and well_known:
            q, label = "검증된성장주", "유명하지만 곡괭이 구조는 약함 -완성품/테마주 성격"
        else:
            q, label = "관심밖", "곡괭이도 아니고 싸기만 함 -싼 데는 보통 이유가 있음"

        return Classified(
            code=shovel.code, name=shovel.name,
            shovel_score=shovel.total, recognition=recog,
            quadrant=q, label=label,
        )

    def split_recommendations(self, classifieds: list[Classified]) -> dict:
        """
        추천을 두 바구니로 나눠서 반환:
            'proven'  = 이미 성장한 검증된 곡괭이 (안정 추구)
            'hidden'  = 아직 저평가된 숨은 곡괭이 (고위험·고수익)
        """
        proven = sorted(
            [c for c in classifieds if c.quadrant == "핵심곡괭이"],
            key=lambda c: c.shovel_score, reverse=True)
        hidden = sorted(
            [c for c in classifieds if c.quadrant == "숨은곡괭이"],
            key=lambda c: c.shovel_score, reverse=True)
        return {"proven": proven, "hidden": hidden}
