"""
ValueChain 주식 추천 플랫폼 메인 진입점.

실행: python main.py

흐름:
  ① 뉴스 기반 핫 섹터 자동 감지
  ② 섹터별 밸류체인 구성
  ③ 실 재무·시세 데이터 수집 (yfinance)
  ④ 곡괭이 점수 + 4분면 분류
  ⑤ BUY / HOLD / SELL 판정 + 근거 출력

※ 투자 자문 아님. 후보 추리기 참고 자료.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from news.theme import detect_hot_sectors
from data.sectors import get_chain
from data.realdata import YfinanceDataProvider
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier
from analysis.verdict import make_verdict

DIVIDER = "=" * 72


def run_sector(sector_name: str, headlines: list[str]):
    print(f"\n{DIVIDER}")
    print(f"  섹터: {sector_name}")
    print(f"  관련 뉴스:")
    for h in headlines:
        print(f"    - {h[:60]}")
    print(DIVIDER)

    # ① 밸류체인 그래프
    vc = get_chain(sector_name)
    if vc is None:
        print(f"  [스킵] '{sector_name}' 밸류체인 템플릿 없음")
        return

    codes = list(vc.g.nodes())
    print(f"\n  대상 종목: {len(codes)}개")

    # ② 실 데이터 수집
    print("  실 데이터 수집 중 (Yahoo Finance)...")
    provider = YfinanceDataProvider()
    all_data = provider.fetch_many(codes)

    if not all_data:
        print("  데이터 수집 실패")
        return

    # ③ 곡괭이 점수
    det = ShovelDetector(vc)
    clf = MaturityClassifier()
    fin_map = {c: d.financials for c, d in all_data.items()}
    scores = det.rank(fin_map)

    # ④ 4분면 분류 + 판정
    verdicts = []
    for s in scores:
        d = all_data.get(s.code)
        if not d:
            continue
        classified = clf.classify(s, d.market_signals)
        v = make_verdict(classified, s, d.market_signals, d)
        verdicts.append(v)

    # ⑤ 출력
    _print_summary_table(verdicts)
    _print_detailed(verdicts)


def _print_summary_table(verdicts):
    print(f"\n  {'종목명':<14} {'판정':^6} {'확신':^4} {'곡괭이':>6} {'매출성장':>8} {'영익률':>7} {'PER':>7} {'1년수익률':>9} {'4분면'}")
    print("  " + "-" * 76)
    icons = {"BUY": "▲ BUY", "HOLD": "- HOL", "SELL": "▼ SEL", "AVOID": "× AVD"}
    conf_icons = {"높음": "●●", "중간": "●○", "낮음": "○○"}
    for v in verdicts:
        m = v.metrics
        icon = icons.get(v.action, v.action)
        conf = conf_icons.get(v.confidence, "  ")
        name = v.name[:13]
        print(f"  {name:<14} {icon:<6} {conf:<4} "
              f"{m['곡괭이점수']:>6} {m['매출성장']:>8} {m['영업이익률']:>7} "
              f"{m['PER']:>7} {m['1년수익률']:>9}  {m['4분면']}")


def _print_detailed(verdicts):
    buy_list  = [v for v in verdicts if v.action == "BUY"]
    hold_list = [v for v in verdicts if v.action == "HOLD"]
    sell_list = [v for v in verdicts if v.action in ("SELL", "AVOID")]

    if buy_list:
        print(f"\n  ★ BUY 추천 ({len(buy_list)}종목)")
        print("  " + "-" * 50)
        for v in buy_list:
            print(f"\n  [{v.action}] {v.name}  (확신: {v.confidence})")
            for r in v.reasons:
                print(f"    • {r}")

    if hold_list:
        print(f"\n  - HOLD ({len(hold_list)}종목)")
        print("  " + "-" * 50)
        for v in hold_list:
            print(f"  {v.name}: {v.reasons[-1]}")

    if sell_list:
        print(f"\n  ▼ SELL/AVOID ({len(sell_list)}종목)")
        print("  " + "-" * 50)
        for v in sell_list:
            print(f"  {v.name}: {v.reasons[-1]}")


def main():
    print(DIVIDER)
    print("  ValueChain 주식 추천 플랫폼")
    print("  ※ 투자 자문 아님. 후보 추리기 참고 자료.")
    print(DIVIDER)

    # ① 핫 섹터 감지
    hot = detect_hot_sectors(top_n=2)

    print(f"\n  이번 주 핫 섹터 TOP {len(hot)}:")
    for i, h in enumerate(hot, 1):
        print(f"    {i}위 [{h.sector}] 기사 {h.heat}건")

    # ② 섹터별 분석 실행
    for h in hot:
        run_sector(h.sector, h.top_headlines)

    print(f"\n{DIVIDER}")
    print("  분석 완료. 결과는 후보 추리기용 참고 자료입니다.")
    print(DIVIDER)


if __name__ == "__main__":
    main()
