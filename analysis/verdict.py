"""
BUY / HOLD / SELL 판정 엔진.

AI 없이 규칙 기반으로 판정한다.
모든 판정에는 수치 근거를 함께 출력한다.

판정 기준:
    BUY  - 곡괭이 강함(>=0.50) + 저평가(숨은곡괭이) + 재무실체 있음(>=0.30)
    BUY  - 곡괭이 강함 + 재무실체 강함(>=0.65) + 1년수익률 낮음(<50%)
    HOLD - 곡괭이 강함 + 이미 고평가(핵심곡괭이)
    HOLD - 곡괭이 중간(0.35~0.50) + 재무 양호
    SELL - 재무실체 약함(<0.20) → 스토리만 있고 돈 못 버는 함정
    SELL - 곡괭이 약함(<0.35) + 고평가(검증된성장주)
    AVOID- 곡괭이 약함 + 저평가 = 싼 데는 이유가 있음
"""
from __future__ import annotations
from dataclasses import dataclass
from analysis.shovel import ShovelScore
from analysis.maturity import Classified, MarketSignals
from data.realdata import CompanyRealData


@dataclass
class Verdict:
    code: str
    name: str
    action: str          # "BUY" | "HOLD" | "SELL" | "AVOID"
    confidence: str      # "높음" | "중간" | "낮음"
    reasons: list[str]   # 판정 근거 (수치 포함)
    metrics: dict        # 핵심 지표 요약


def make_verdict(classified: Classified,
                 shovel: ShovelScore,
                 sig: MarketSignals,
                 real: CompanyRealData) -> Verdict:
    """단일 종목 BUY/HOLD/SELL 판정."""
    f = real.financials
    reasons: list[str] = []
    action = "HOLD"
    confidence = "중간"

    # ── 재무 지표 수집 ──────────────────────────────────────────────────
    fin_reality = shovel.financial_reality
    shovel_total = shovel.total
    q = classified.quadrant
    ret_1y = sig.price_return_1y
    per = sig.per

    # ── 근거 문장 생성 ──────────────────────────────────────────────────
    if f.revenue_growth_yoy > 0:
        reasons.append(f"매출 전년比 +{f.revenue_growth_yoy:.1f}% 성장")
    else:
        reasons.append(f"매출 전년比 {f.revenue_growth_yoy:.1f}% 역성장")

    if f.op_margin > 0:
        reasons.append(f"영업이익률 {f.op_margin:.1f}%")
    if f.op_profit_growth_yoy > 0:
        reasons.append(f"영업이익 전년比 +{f.op_profit_growth_yoy:.1f}% 성장")

    reasons.append(f"밸류체인 위치: {_tier_desc(shovel)}")
    reasons.append(f"곡괭이 점수 {shovel_total:.3f} "
                   f"(대체불가 {shovel.irreplaceability:.2f} / "
                   f"고객분산 {shovel.customer_spread:.2f})")

    if per:
        reasons.append(f"PER {per:.1f}배")
    reasons.append(f"최근 1년 주가 {ret_1y:+.0f}%")

    # ── 판정 규칙 ───────────────────────────────────────────────────────
    if fin_reality < 0.20:
        action = "SELL"
        confidence = "높음"
        reasons.append("▶ 재무실체 약함 — 스토리만 있고 실적 미확인")

    elif q == "숨은곡괭이" and fin_reality >= 0.30:
        action = "BUY"
        confidence = "높음"
        reasons.append("▶ 곡괭이 구조 강함 + 시장 저평가 — 재평가 여력 있음")

    elif q == "숨은곡괭이" and fin_reality < 0.30:
        action = "BUY"
        confidence = "낮음"
        reasons.append("▶ 구조는 좋으나 재무 개선 추세 확인 필요")

    elif q == "핵심곡괭이":
        action = "HOLD"
        confidence = "높음"
        reasons.append("▶ 검증된 곡괭이지만 시장이 이미 알아봄 — 추가 상승여력 제한")

    elif q == "검증된성장주" and shovel_total < 0.35:
        action = "SELL"
        confidence = "중간"
        reasons.append("▶ 곡괭이 구조 약함 + 고평가 — 테마/완성품 성격")

    elif q == "관심밖":
        action = "AVOID"
        confidence = "중간"
        reasons.append("▶ 곡괭이 구조 약함 — 싼 데는 이유가 있음")

    elif shovel_total >= 0.50 and fin_reality >= 0.65 and ret_1y < 50:
        action = "BUY"
        confidence = "중간"
        reasons.append("▶ 곡괭이 강함 + 실적 탄탄 + 주가 아직 덜 오름")

    else:
        action = "HOLD"
        reasons.append("▶ 구조·실적 양호하나 확실한 매수 트리거 없음")

    metrics = {
        "현재가":     f"{sig.market_cap/1e12:.1f}조 시총" if sig.market_cap else "N/A",
        "매출성장":   f"{f.revenue_growth_yoy:+.1f}%",
        "영업이익률": f"{f.op_margin:.1f}%",
        "영익성장":   f"{f.op_profit_growth_yoy:+.1f}%",
        "PER":        f"{per:.1f}배" if per else "N/A",
        "1년수익률":  f"{ret_1y:+.0f}%",
        "곡괭이점수": f"{shovel_total:.3f}",
        "4분면":      q,
    }

    return Verdict(code=classified.code, name=classified.name,
                   action=action, confidence=confidence,
                   reasons=reasons, metrics=metrics)


def _tier_desc(s: ShovelScore) -> str:
    if s.upstream_position >= 0.8:
        return "밸류체인 최상류 핵심 공급사"
    elif s.upstream_position >= 0.5:
        return "중간 공급단"
    else:
        return "완성품/하류"
