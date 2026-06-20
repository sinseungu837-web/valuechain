"""
실 데이터 파이프라인 데모.

yfinance에서 실제 시세·재무를 자동 수집해서 전체 파이프라인을 돌린다.
밸류체인 그래프(공급관계)는 수동 구성 (자동화 불가 영역).

실행: python demo_real.py
※ 투자 자문 아님. 결과는 후보 추리기용 참고 자료.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from demo import build_semiconductor_chain
from data.realdata import YfinanceDataProvider
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier


def main():
    codes = ["042700", "403870", "240810", "058470", "095340", "000660", "005930"]

    # ① 밸류체인 그래프 (공급관계는 수동)
    vc = build_semiconductor_chain()

    # ② 실 데이터 수집
    print("실 데이터 수집 중 (Yahoo Finance)...")
    provider = YfinanceDataProvider(market="KS")
    all_data = provider.fetch_many(codes)

    if not all_data:
        print("데이터 수집 실패. 인터넷 연결을 확인하세요.")
        return

    # 수집 결과 요약
    print(f"\n{'종목코드':<8} {'종목명':<22} {'현재가':>10} {'매출성장':>8} {'영익률':>8} {'영익성장':>8} {'1년수익률':>10}")
    print("-" * 78)
    for code in codes:
        d = all_data.get(code)
        if not d:
            print(f"{code:<8} 수집 실패")
            continue
        f = d.financials
        s = d.market_signals
        short_name = d.name[:20]
        mc_str = f"{s.market_cap/1e12:.0f}조" if s.market_cap else "N/A"
        print(f"{code:<8} {short_name:<22} {s.market_cap and f'{s.market_cap/1e12:.0f}조':>10}"
              f" {f.revenue_growth_yoy:>+7.1f}%"
              f" {f.op_margin:>7.1f}%"
              f" {f.op_profit_growth_yoy:>+7.1f}%"
              f" {s.price_return_1y:>+9.1f}%")

    # ③ 곡괭이 점수
    det = ShovelDetector(vc)
    financials_map = {code: d.financials for code, d in all_data.items()}
    scores = det.rank(financials_map)

    print("\n" + "=" * 72)
    print("  곡괭이 점수 랭킹 (실 재무 기반)")
    print("=" * 72)
    print(f"  {'순위':<4} {'종목명':<12} {'총점':>6} {'대체불가':>8} {'고객분산':>8} {'상류위치':>8} {'재무실체':>8}")
    print("  " + "-" * 60)
    for i, s in enumerate(scores, 1):
        print(f"  {i:<4} {s.name:<12} {s.total:>6.3f} {s.irreplaceability:>8.3f}"
              f" {s.customer_spread:>8.3f} {s.upstream_position:>8.3f}"
              f" {s.financial_reality:>8.3f}")

    # ④ 4분면 분류
    clf = MaturityClassifier()
    signals_map = {code: d.market_signals for code, d in all_data.items()}

    classifieds = []
    for s in scores:
        sig = signals_map.get(s.code)
        if sig:
            classifieds.append(clf.classify(s, sig))

    print("\n" + "=" * 72)
    print("  4분면 분류 결과 (실 시장 데이터 기반)")
    print("=" * 72)
    for c in classifieds:
        per_str = f"PER {signals_map[c.code].per:.1f}" if signals_map[c.code].per else "PER N/A"
        ret_str = f"1년 {signals_map[c.code].price_return_1y:+.0f}%"
        print(f"\n  {c.name[:12]:<12} | 곡괭이 {c.shovel_score:.3f} | 시장인식 {c.recognition:.3f}"
              f" | {per_str} | {ret_str}")
        print(f"  └─ [{c.quadrant}] {c.label}")

    # ⑤ 추천 바구니
    rec = clf.split_recommendations(classifieds)

    print("\n" + "=" * 72)
    print("  ■ 추천 A: 검증된 곡괭이 (이미 시장이 알아봄)")
    print("=" * 72)
    if rec["proven"]:
        for c in rec["proven"]:
            print(f"    • {c.name} (곡괭이 {c.shovel_score:.3f})")
    else:
        print("    (해당 없음)")

    print("\n" + "=" * 72)
    print("  ■ 추천 B: 숨은 곡괭이 ★ (구조는 좋은데 저평가)")
    print("=" * 72)
    if rec["hidden"]:
        for c in rec["hidden"]:
            sig = signals_map[c.code]
            print(f"    • {c.name} (곡괭이 {c.shovel_score:.3f} | 시장인식 {c.recognition:.3f})")
            per_str = f"PER {sig.per:.1f}" if sig.per else "PER N/A"
            mc_str = f"시총 {sig.market_cap/1e12:.1f}조" if sig.market_cap else ""
            print(f"      → {per_str} | {mc_str} | 1년 수익률 {sig.price_return_1y:+.0f}%")
    else:
        print("    (해당 없음)")

    print("\n※ 투자 자문 아님. 후보 추리기 참고 자료.")


if __name__ == "__main__":
    main()
