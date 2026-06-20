"""
통합 데모: 데이터소스 + 밸류체인 그래프 + (멀티AI용) 컨텍스트 생성.
반도체 밸류체인 샘플로 충격 전파를 실제 계산한다.
실행: python3 demo.py
"""
import sys
sys.path.insert(0, "/home/claude/valuechain")

from data.source import SampleSource
from core.graph import ValueChain, Company


def build_semiconductor_chain() -> ValueChain:
    vc = ValueChain("반도체")

    # 밸류체인 단계별 기업 등록 (tier = 상류->하류)
    companies = [
        Company("042700", "한미반도체", "장비",   ["TC본더", "HBM후공정"]),
        Company("403870", "HPSP",      "장비",   ["고압수소어닐링"]),
        Company("240810", "원익IPS",   "장비",   ["증착장비"]),
        Company("058470", "리노공업",  "부품",   ["테스트소켓"]),
        Company("095340", "ISC",       "부품",   ["테스트소켓"]),
        Company("000660", "SK하이닉스","제조",   ["HBM", "DRAM"]),
        Company("005930", "삼성전자",  "제조",   ["HBM", "DRAM", "파운드리"]),
    ]
    for c in companies:
        vc.add_company(c)

    # 공급 관계: 장비/부품 -> 제조사 (weight=제조사의 의존도)
    vc.supplies("042700", "000660", 0.55)   # 한미반도체 -> 하이닉스 (HBM 본더 핵심)
    vc.supplies("042700", "005930", 0.30)
    vc.supplies("403870", "000660", 0.25)
    vc.supplies("403870", "005930", 0.25)
    vc.supplies("240810", "005930", 0.20)
    vc.supplies("058470", "000660", 0.15)
    vc.supplies("058470", "005930", 0.15)
    vc.supplies("095340", "000660", 0.12)

    # 경쟁 관계
    vc.competes("058470", "095340", 0.7)    # 리노공업 vs ISC (테스트소켓)
    vc.competes("000660", "005930", 0.5)    # 하이닉스 vs 삼성 (메모리)

    return vc


def make_ai_context(vc: ValueChain, src: SampleSource, focus: str) -> str:
    """밸류체인+시세를 멀티AI에게 넘길 텍스트로 직렬화 (환각 방지용 근거 데이터)."""
    codes = list(vc.g.nodes())
    quotes = src.get_quotes(codes)

    lines = [f"=== {vc.industry} 밸류체인 분석 컨텍스트 ===", ""]
    lines.append("[기업 시세]")
    for code in codes:
        q = quotes[code]
        node = vc.g.nodes[code]
        lines.append(
            f"  {q.name}({code}) | 단계:{node['tier']} | "
            f"가격:{q.price:,}원 | 시총:{q.market_cap/1e12:.1f}조 | "
            f"등락:{q.change_pct:+.1f}% | PER:{q.per} | 기술:{node['technologies']}"
        )

    lines.append("")
    lines.append(f"[{vc.g.nodes[focus]['name']} 기준 밸류체인 위치]")
    up = vc.upstream_of(focus)
    down = vc.downstream_of(focus)
    lines.append(f"  상류(공급사): {[vc.g.nodes[c]['name'] for c in up] or '없음'}")
    lines.append(f"  하류(고객사): {[vc.g.nodes[c]['name'] for c in down] or '없음'}")
    return "\n".join(lines)


if __name__ == "__main__":
    src = SampleSource()
    vc = build_semiconductor_chain()

    print(vc.summary())
    print()

    # --- 충격 전파 시뮬레이션 -------------------------------------------
    print("■ 시나리오: 한미반도체(042700)에 강한 악재(-1.0) 발생")
    print("  (예: HBM 본더 핵심 고객 발주 지연)\n")
    impact = vc.propagate_shock("042700", magnitude=-1.0)

    print("  충격 전파 결과 (음수=악영향, 양수=반사이익):")
    for code, val in sorted(impact.items(), key=lambda x: x[1]):
        name = vc.g.nodes[code]["name"]
        bar = "▼" * int(abs(val) * 20) if val < 0 else "▲" * int(val * 20)
        print(f"    {name:10s} {val:+.3f}  {bar}")

    print()
    # --- 기술 노출도 ----------------------------------------------------
    print("■ 'HBM' 기술을 핵심으로 보유한 기업:")
    for code in vc.tech_exposure("HBM"):
        print(f"    - {vc.g.nodes[code]['name']}")

    print()
    # --- 멀티AI에게 넘길 컨텍스트 미리보기 ------------------------------
    print("■ 멀티AI 분석 엔진에 전달될 컨텍스트:")
    print(make_ai_context(vc, src, focus="000660"))
