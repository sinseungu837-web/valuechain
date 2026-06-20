"""
밸류체인 그래프 엔진.

산업 = 방향성 그래프(directed graph)
    노드 = 기업 (시총, 섹터, 핵심기술 보유)
    엣지 = 관계
        SUPPLIES  : A가 B에게 납품한다 (A -> B)
        COMPETES  : A와 B는 경쟁한다 (양방향)
        SUBSTITUTE: A가 B를 대체할 수 있다

엣지 weight = 의존도 (0~1). '매출 비중' 또는 '대체 불가능성'으로 해석.

핵심 기능:
    1. 밸류체인 위치 파악 (상류/하류)
    2. 충격 전파 (shock propagation):
       특정 노드/기술이 흔들릴 때 영향을 받는 기업과 강도를 계산
"""
from __future__ import annotations
from dataclasses import dataclass, field
import networkx as nx


@dataclass
class Company:
    code: str
    name: str
    tier: str               # 밸류체인 단계: 소재/장비/파운드리/팹리스/세트 등
    technologies: list[str] = field(default_factory=list)  # 핵심 기술 태그


class ValueChain:
    def __init__(self, industry: str):
        self.industry = industry
        self.g = nx.DiGraph()

    # --- 그래프 구성 ----------------------------------------------------
    def add_company(self, c: Company):
        self.g.add_node(c.code, **c.__dict__)

    def supplies(self, supplier: str, customer: str, dependency: float):
        """supplier가 customer에게 납품. dependency=customer가 받는 의존도."""
        self.g.add_edge(supplier, customer, rel="SUPPLIES", weight=dependency)

    def competes(self, a: str, b: str, intensity: float):
        self.g.add_edge(a, b, rel="COMPETES", weight=intensity)
        self.g.add_edge(b, a, rel="COMPETES", weight=intensity)

    # --- 분석 -----------------------------------------------------------
    def upstream_of(self, code: str) -> list[str]:
        """이 기업에 납품하는 상류(공급사)들."""
        return [u for u, v, d in self.g.in_edges(code, data=True)
                if d["rel"] == "SUPPLIES"]

    def downstream_of(self, code: str) -> list[str]:
        """이 기업의 제품을 받는 하류(고객사)들."""
        return [v for u, v, d in self.g.out_edges(code, data=True)
                if d["rel"] == "SUPPLIES"]

    def propagate_shock(self, origin: str, magnitude: float,
                        decay: float = 0.6, max_depth: int = 4) -> dict[str, float]:
        """
        origin 기업에 magnitude(예: -1.0=강한 악재) 충격 발생 시
        밸류체인을 따라 충격이 어떻게 전파되는지 계산.

        SUPPLIES 관계를 따라 하류(고객)로 전파:
            고객이 받는 충격 = 상류 충격 * 의존도(weight) * decay
        COMPETES 관계는 반대 부호로 전파(경쟁사 악재 = 반사이익):
            경쟁사 충격 = -상류 충격 * intensity * decay * 0.5

        반환: {종목코드: 누적 충격값}
        """
        impact: dict[str, float] = {origin: magnitude}
        frontier = [(origin, magnitude, 0)]

        while frontier:
            node, force, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for _, nxt, d in self.g.out_edges(node, data=True):
                if d["rel"] == "SUPPLIES":
                    transmitted = force * d["weight"] * decay
                elif d["rel"] == "COMPETES":
                    transmitted = -force * d["weight"] * decay * 0.5
                else:
                    continue
                if abs(transmitted) < 0.02:   # 미미하면 컷
                    continue
                impact[nxt] = impact.get(nxt, 0.0) + transmitted
                frontier.append((nxt, transmitted, depth + 1))
        return impact

    def tech_exposure(self, technology: str) -> list[str]:
        """특정 기술을 핵심으로 보유한 기업들 (기술이 산업을 좌우하는지 분석용)."""
        return [n for n, d in self.g.nodes(data=True)
                if technology in d.get("technologies", [])]

    def summary(self) -> dict:
        return {
            "industry": self.industry,
            "companies": self.g.number_of_nodes(),
            "relations": self.g.number_of_edges(),
        }
