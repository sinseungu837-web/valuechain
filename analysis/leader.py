"""
대장주 랭킹 (V3).

대장주 = "지금 산업에서 큰 기업" (곡괭이 점수와는 별개 축).
설계 확정 공식:
    대장주 점수 = 0.35×매출순위 + 0.35×영업이익순위 + 0.30×점유율
    (각 지표는 섹터 내에서 0~1 정규화)

점유율 데이터가 전혀 없으면(모두 0) 0.30 가중치를 빼고
매출·영익만으로 0.5/0.5 재정규화한다.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class LeaderScore:
    code: str
    name: str
    revenue: float        # 절대 매출
    op_income: float      # 절대 영업이익
    market_share: float   # 0~1
    rev_norm: float       # 0~1
    op_norm: float        # 0~1
    total: float          # 대장주 점수 0~1


def _minmax(values: dict[str, float]) -> dict[str, float]:
    """값 dict를 0~1로 정규화. 모두 같으면 0.5."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi <= lo:
        return {k: 0.5 for k in values}
    return {k: (v - lo) / (hi - lo) for k, v in values.items()}


def rank_leaders(companies: list[dict],
                 real_map: dict) -> list[LeaderScore]:
    """
    companies: 섹터 JSON의 종목 목록 (code, name, market_share)
    real_map:  {code: CompanyRealData} (yfinance)
    """
    rev = {}
    op = {}
    share = {}
    meta = {}
    for c in companies:
        code = str(c["code"])
        rd = real_map.get(code)
        rev[code] = rd.financials.revenue if rd else 0.0
        op[code] = rd.financials.op_income if rd else 0.0
        share[code] = float(c.get("market_share", 0.0))
        meta[code] = c.get("name", code)

    rev_n = _minmax(rev)
    op_n = _minmax(op)

    has_share = any(v > 0 for v in share.values())
    if has_share:
        w_rev, w_op, w_share = 0.35, 0.35, 0.30
    else:
        w_rev, w_op, w_share = 0.5, 0.5, 0.0   # 점유율 없으면 재정규화

    out = []
    for code in rev:
        total = (w_rev * rev_n.get(code, 0)
                 + w_op * op_n.get(code, 0)
                 + w_share * share.get(code, 0))
        out.append(LeaderScore(
            code=code, name=meta[code],
            revenue=rev[code], op_income=op[code],
            market_share=share[code],
            rev_norm=round(rev_n.get(code, 0), 3),
            op_norm=round(op_n.get(code, 0), 3),
            total=round(total, 3),
        ))
    return sorted(out, key=lambda x: x.total, reverse=True)
