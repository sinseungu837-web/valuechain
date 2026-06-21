"""
섹터 JSON 스토어 (V3).

섹터 하나 = JSON 파일 하나 (sectors/{name}.json).
사용자가 만들고 키워가는 '구조 정보' 자산.
시세·재무는 여기 저장하지 않는다(yfinance로 실시간 조회). 구조만 저장.

스키마:
{
  "sector": "로봇",
  "functional_blocks": ["두뇌", "시야", "관절", ...],   # 이 산업의 기능 부품 블록
  "companies": [
    {"code": "277810", "name": "레인보우로보틱스",
     "functional_blocks": ["판단", "골격"],
     "market_share": 0.15, "is_final_product": true}
  ],
  "supply_relations": [
    {"from": "부품사코드", "to": "완성품코드",
     "block": "관절", "part": "감속기", "dependency": 0.6}
  ]
}
"""
from __future__ import annotations
import os
import json
import glob
from core.graph import ValueChain, Company

# 섹터 JSON 저장 폴더 (프로젝트 루트의 sectors/)
SECTORS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "sectors")
)


def _path(sector_name: str) -> str:
    return os.path.join(SECTORS_DIR, f"{sector_name}.json")


def list_sectors() -> list[str]:
    """저장된 섹터 이름 목록."""
    if not os.path.isdir(SECTORS_DIR):
        return []
    files = glob.glob(os.path.join(SECTORS_DIR, "*.json"))
    return sorted(os.path.splitext(os.path.basename(f))[0] for f in files)


def load_sector(sector_name: str) -> dict | None:
    """섹터 JSON 로드. 없으면 None."""
    p = _path(sector_name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_sector(data: dict) -> str:
    """섹터 JSON 저장. data['sector']를 파일명으로. 저장 경로 반환."""
    os.makedirs(SECTORS_DIR, exist_ok=True)
    name = data["sector"]
    p = _path(name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def empty_sector(sector_name: str) -> dict:
    """빈 섹터 스키마 생성 (새 섹터 시작용)."""
    return {
        "sector": sector_name,
        "functional_blocks": [],
        "companies": [],
        "supply_relations": [],
    }


def build_chain(data: dict) -> ValueChain:
    """
    섹터 JSON → ValueChain 그래프.
    기존 엔진(shovel/maturity)이 그대로 소비할 수 있는 형태로 만든다.
    """
    vc = ValueChain(data.get("sector", "?"))

    for c in data.get("companies", []):
        blocks = c.get("functional_blocks", [])
        vc.add_company(Company(
            code=str(c["code"]),
            name=c["name"],
            # tier: 완성품이면 '완성품', 아니면 담당 블록 첫 항목(없으면 '부품')
            tier="완성품" if c.get("is_final_product") else (
                blocks[0] if blocks else "부품"),
            technologies=c.get("technologies", []),
            functional_blocks=blocks,
            market_share=float(c.get("market_share", 0.0)),
            is_final_product=bool(c.get("is_final_product", False)),
        ))

    for r in data.get("supply_relations", []):
        frm, to = str(r["from"]), str(r["to"])
        # 그래프에 두 노드가 모두 있어야 엣지 연결
        if frm in vc.g.nodes and to in vc.g.nodes:
            vc.supplies(frm, to, float(r.get("dependency", 0.0)))

    return vc
