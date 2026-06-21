"""
곡괭이 기업 탐지기 (Picks & Shovels Detector).

골드러시 비유의 데이터 번역:
    "금을 캐는 사람(완성품 제조사)이 아니라
     곡괭이/청바지를 파는 사람(필수 공급사)을 찾는다."

곡괭이 기업의 4가지 객관적 특징을 점수화:
    1. irreplaceability  대체 불가능성 : 빠지면 밸류체인이 멈추는가
    2. customer_spread   고객 분산     : 산업 전체에 납품하는가 (누가 이기든 돈 번다)
    3. upstream_position 상류 위치     : 완성품 아래 필수 공급단에 있는가
    4. financial_reality 재무 실체     : 매출·영업이익이 실제로 찍히는가

주가나 시총 절대값으로 판단하지 않는다. '구조'와 '실적'으로 판단한다.
모든 입력은 객관적 데이터(그래프 관계 + 재무지표)에서만 나온다.
"""
from __future__ import annotations
from dataclasses import dataclass
from core.graph import ValueChain


@dataclass
class Financials:
    """재무 실체 데이터 (DART 공시 등에서 채움)."""
    code: str
    revenue_growth_yoy: float    # 매출 성장률 (전년比, %)
    op_margin: float             # 영업이익률 (%)
    op_profit_growth_yoy: float  # 영업이익 성장률 (%)
    order_backlog_ratio: float   # 수주잔고/연매출 배수 (없으면 0)
    revenue: float = 0.0         # 절대 매출 (원) — 대장주 랭킹용
    op_income: float = 0.0       # 절대 영업이익 (원) — 대장주 랭킹용


@dataclass
class ShovelScore:
    code: str
    name: str
    irreplaceability: float   # 0~1
    customer_spread: float    # 0~1
    upstream_position: float  # 0~1
    financial_reality: float  # 0~1
    total: float              # 가중합 0~1

    def explain(self) -> list[str]:
        """왜 이 점수가 나왔는지 사람이 읽는 근거 (멀티AI 컨텍스트로도 사용)."""
        out = []
        out.append(f"대체불가성 {self.irreplaceability:.2f}: "
                   f"{'핵심 공급단, 빠지면 밸류체인 정지' if self.irreplaceability>0.6 else '대체 가능성 있음'}")
        out.append(f"고객분산 {self.customer_spread:.2f}: "
                   f"{'산업 전반 납품(곡괭이형)' if self.customer_spread>0.6 else '소수 고객 의존'}")
        out.append(f"상류위치 {self.upstream_position:.2f}: "
                   f"{'완성품 아래 공급단' if self.upstream_position>0.5 else '완성품/하류'}")
        out.append(f"재무실체 {self.financial_reality:.2f}: "
                   f"{'실적이 실제로 성장' if self.financial_reality>0.6 else '실적 근거 약함'}")
        return out


class ShovelDetector:
    # 가중치: 구조(대체불가+분산)를 재무보다 약간 더 본다.
    # 단, 재무실체가 0이면 '스토리만 있고 돈은 안 버는' 함정이라 페널티.
    W = {
        "irreplaceability": 0.30,
        "customer_spread": 0.25,
        "upstream_position": 0.15,
        "financial_reality": 0.30,
    }

    def __init__(self, vc: ValueChain):
        self.vc = vc

    def _irreplaceability(self, code: str) -> float:
        """하류 고객들이 이 회사에 거는 의존도(weight)의 최댓값에 가깝게."""
        outs = [d["weight"] for _, _, d in self.vc.g.out_edges(code, data=True)
                if d["rel"] == "SUPPLIES"]
        if not outs:
            return 0.0
        # 가장 강하게 의존하는 고객의 의존도를 핵심 신호로
        return min(1.0, max(outs) * 1.4)

    def _customer_spread(self, code: str) -> float:
        """납품하는 고객 수가 많을수록 '누가 이기든 돈 버는' 곡괭이형."""
        n = len(self.vc.downstream_of(code))
        # 3곳 이상이면 충분히 분산된 것으로 봄
        return min(1.0, n / 3.0)

    def _upstream_position(self, code: str) -> float:
        """하류(고객)는 있고 상류(공급)는 적을수록 공급단 상류."""
        down = len(self.vc.downstream_of(code))
        up = len(self.vc.upstream_of(code))
        if down == 0:
            return 0.0  # 아무에게도 납품 안 하면 완성품/하류
        return min(1.0, down / (down + up + 1) * 1.5)

    def _financial_reality(self, fin: Financials | None) -> float:
        """매출·영업이익 성장 + 마진 + 수주잔고로 '돈이 진짜 들어오는지'."""
        if fin is None:
            return 0.0
        s = 0.0
        s += min(1.0, max(0, fin.revenue_growth_yoy) / 30.0) * 0.30      # 매출성장 30%면 만점
        s += min(1.0, max(0, fin.op_profit_growth_yoy) / 40.0) * 0.30    # 영익성장 40%면 만점
        s += min(1.0, max(0, fin.op_margin) / 25.0) * 0.25               # 영익률 25%면 만점
        s += min(1.0, fin.order_backlog_ratio / 2.0) * 0.15              # 수주잔고 2년치면 만점
        return s

    def score(self, code: str, fin: Financials | None = None) -> ShovelScore:
        irr = self._irreplaceability(code)
        spr = self._customer_spread(code)
        ups = self._upstream_position(code)
        finr = self._financial_reality(fin)

        total = (self.W["irreplaceability"] * irr +
                 self.W["customer_spread"] * spr +
                 self.W["upstream_position"] * ups +
                 self.W["financial_reality"] * finr)

        # 함정 페널티: 구조는 좋아 보여도 재무실체가 바닥이면 신뢰도 깎음
        if finr < 0.2:
            total *= 0.7

        return ShovelScore(
            code=code, name=self.vc.g.nodes[code]["name"],
            irreplaceability=round(irr, 3), customer_spread=round(spr, 3),
            upstream_position=round(ups, 3), financial_reality=round(finr, 3),
            total=round(total, 3),
        )

    def rank(self, financials: dict[str, Financials]) -> list[ShovelScore]:
        """전체 종목을 곡괭이 점수로 정렬."""
        scores = [self.score(code, financials.get(code))
                  for code in self.vc.g.nodes()]
        return sorted(scores, key=lambda s: s.total, reverse=True)
