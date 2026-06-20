"""곡괭이 탐지기 데모. 실행: python3 demo_shovel.py"""
import sys
sys.path.insert(0, "/home/claude/valuechain")

from demo import build_semiconductor_chain
from analysis.shovel import ShovelDetector, Financials

vc = build_semiconductor_chain()
det = ShovelDetector(vc)

# 가상 재무 데이터 (실제론 DART 공시에서 채움)
# 일부러 함정도 섞음: 원익IPS는 구조는 공급단인데 실적이 약함
fin = {
    "042700": Financials("042700", revenue_growth_yoy=45, op_margin=22, op_profit_growth_yoy=60, order_backlog_ratio=1.8),  # 한미반도체: 호실적
    "403870": Financials("403870", revenue_growth_yoy=30, op_margin=40, op_profit_growth_yoy=35, order_backlog_ratio=1.2),  # HPSP: 고마진 독점
    "240810": Financials("240810", revenue_growth_yoy=2,  op_margin=8,  op_profit_growth_yoy=-10, order_backlog_ratio=0.3), # 원익IPS: 실적 약함(함정)
    "058470": Financials("058470", revenue_growth_yoy=15, op_margin=30, op_profit_growth_yoy=12, order_backlog_ratio=0.5),  # 리노공업: 꾸준
    "095340": Financials("095340", revenue_growth_yoy=20, op_margin=18, op_profit_growth_yoy=25, order_backlog_ratio=0.4),  # ISC
    "000660": Financials("000660", revenue_growth_yoy=50, op_margin=35, op_profit_growth_yoy=120, order_backlog_ratio=0.8), # SK하이닉스: 완성품(금 캐는 쪽)
    "005930": Financials("005930", revenue_growth_yoy=12, op_margin=15, op_profit_growth_yoy=20, order_backlog_ratio=0.5),  # 삼성전자
}

print("=" * 70)
print("  곡괭이 기업 랭킹 (반도체 밸류체인)")
print("  높을수록 '누가 금을 캐든 곡괭이를 파는' 구조 + 실적 보유")
print("=" * 70)

for i, s in enumerate(det.rank(fin), 1):
    tier = vc.g.nodes[s.code]["tier"]
    print(f"\n{i}위  {s.name} ({tier})  ★ 종합 {s.total}")
    print(f"     대체불가 {s.irreplaceability} | 고객분산 {s.customer_spread} | "
          f"상류 {s.upstream_position} | 재무 {s.financial_reality}")

print("\n" + "=" * 70)
print("  1위 종목 상세 근거 (멀티AI에게 넘어갈 형태):")
top = det.rank(fin)[0]
for line in top.explain():
    print(f"    - {line}")
