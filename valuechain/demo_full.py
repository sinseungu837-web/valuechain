"""전체 파이프라인 데모: 곡괭이 점수 + 성숙도 분류. 실행: python3 demo_full.py"""
import sys
sys.path.insert(0, "/home/claude/valuechain")

from demo import build_semiconductor_chain
from analysis.shovel import ShovelDetector, Financials
from analysis.maturity import MaturityClassifier, MarketSignals

vc = build_semiconductor_chain()
det = ShovelDetector(vc)
clf = MaturityClassifier()

fin = {
    "042700": Financials("042700", 45, 22, 60, 1.8),
    "403870": Financials("403870", 30, 40, 35, 1.2),
    "240810": Financials("240810", 2, 8, -10, 0.3),
    "058470": Financials("058470", 15, 30, 12, 0.5),
    "095340": Financials("095340", 20, 18, 25, 0.4),
    "000660": Financials("000660", 50, 35, 120, 0.8),
    "005930": Financials("005930", 12, 15, 20, 0.5),
}

# 시장 인식 신호 (PER, PBR, 1년수익률, 시총)
sig = {
    "042700": MarketSignals("042700", 35, 8.1, 85, 9.5e12),   # 한미: 이미 많이 오름
    "403870": MarketSignals("403870", 28, 9.0, 40, 3.1e12),   # HPSP
    "240810": MarketSignals("240810", 18, 1.7, -15, 1.6e12),  # 원익IPS: 저평가지만 실적약함
    "058470": MarketSignals("058470", 22, 4.5, 10, 2.3e12),   # 리노공업
    "095340": MarketSignals("095340", 24, 3.2, 30, 1.3e12),   # ISC: 저평가+곡괭이성
    "000660": MarketSignals("000660", 9.8, 1.9, 70, 129e12),  # 하이닉스: 대형주
    "005930": MarketSignals("005930", 14, 1.3, 15, 423e12),   # 삼성: 초대형
}

# 1. 곡괭이 점수 → 2. 성숙도 분류
classifieds = []
for s in det.rank(fin):
    c = clf.classify(s, sig[s.code])
    classifieds.append(c)

print("=" * 72)
print("  전체 분류 결과")
print("=" * 72)
for c in classifieds:
    print(f"\n  {c.name:10s} | 곡괭이 {c.shovel_score:.2f} | 시장인식 {c.recognition:.2f}")
    print(f"  └─ [{c.quadrant}] {c.label}")

# 3. 두 바구니로 추천 분리
rec = clf.split_recommendations(classifieds)

print("\n" + "=" * 72)
print("  ■ 추천 A: 이미 검증된 곡괭이 (안정 추구)")
print("=" * 72)
if rec["proven"]:
    for c in rec["proven"]:
        print(f"    • {c.name} (곡괭이 {c.shovel_score:.2f}, 인식 {c.recognition:.2f})")
else:
    print("    (해당 없음)")

print("\n" + "=" * 72)
print("  ■ 추천 B: 아직 저평가된 숨은 곡괭이 ★ (고위험·고수익)")
print("=" * 72)
if rec["hidden"]:
    for c in rec["hidden"]:
        print(f"    • {c.name} (곡괭이 {c.shovel_score:.2f}, 인식 {c.recognition:.2f})")
        print(f"      → 핵심곡괭이와 같은 구조인데 시장이 아직 저평가")
else:
    print("    (해당 없음)")
