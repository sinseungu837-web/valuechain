"""
ValueChain V3 — 산업 구조 해부 도구 (메인).

"섹터를 선택하면, 그 산업을 기능 부품 블록으로 해부하고
누가 어디를 쥐었는지를 객관적 데이터로 보여준다."

예측 아님. 현재 구조 이해. 투자 자문 아님.

두 가지 분석:
  🚀 빠른 분석 — 거래소 전체 업종(161개) 중 선택 → 종목 자동 → 대장주·재무 (구조 불필요)
  🔬 심층 분석 — 사용자가 구조를 정의한 섹터 → 곡괭이 4분면·공급관계까지

시세·재무는 yfinance 자동. 구조(블록·공급관계)는 '🛠️ 섹터 편집' 페이지에서 정의.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(page_title="ValueChain 산업 구조 분석",
                   page_icon="🔬", layout="centered")

from data.sector_store import list_sectors, load_sector, build_chain
from data.market_sectors import get_industries, stocks_in_industry
from data.realdata import YfinanceDataProvider
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier
from analysis.leader import rank_leaders


# ── 캐시 래퍼 ────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def _industries():
    return get_industries()


@st.cache_data(ttl=3600)
def _stocks(industry: str):
    return stocks_in_industry(industry)


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_real(codes: tuple):
    return YfinanceDataProvider().fetch_many(list(codes))


st.title("🔬 ValueChain 산업 구조 분석")
st.caption("산업을 해부해 '누가 어디를 쥐었나'를 봅니다. "
           "예측 아님 · 구조 이해 · 투자 자문 아님.")

mode = st.radio("분석 방식",
                ["🚀 빠른 분석 (전체 업종)", "🔬 심층 분석 (내 섹터)"],
                horizontal=True)
st.divider()


# ════════════════════════════════════════════════════════════════════════
# 🚀 빠른 분석 — 거래소 전체 업종, 구조 정의 불필요
# ════════════════════════════════════════════════════════════════════════
if mode == "🚀 빠른 분석 (전체 업종)":
    st.subheader("🚀 빠른 분석")
    st.caption("거래소 공식 업종을 고르면 시총 상위 종목의 재무를 자동 비교합니다. "
               "구조(곡괭이·공급관계)는 심층 분석에서.")

    inds = _industries()
    industry = st.selectbox("업종 선택", inds)
    top_n = st.slider("분석할 종목 수 (시총 상위)", 5, 20, 12)

    if st.button("분석", type="primary", use_container_width=True):
        cand = _stocks(industry)
        if not cand:
            st.error("해당 업종 종목을 불러오지 못했습니다 (서버 문제 또는 빈 업종).")
            st.stop()

        picked = cand[:top_n]
        codes = tuple(str(s["code"]) for s in picked)
        with st.spinner(f"{industry} {len(codes)}종목 재무 조회 중..."):
            real_map = _fetch_real(codes)

        st.caption(f"자동 조회 {len(real_map)}/{len(codes)}종목 · 출처 Yahoo Finance")
        if not real_map:
            st.error("재무 조회 실패.")
            st.stop()

        # 대장주 랭킹 (점유율 없으니 매출·영익 0.5/0.5)
        comp_list = [{"code": str(s["code"]), "name": s["name"],
                      "market_share": 0.0} for s in picked]
        leaders = rank_leaders(comp_list, real_map)

        import pandas as pd
        st.markdown("### 👑 대장주 랭킹 (매출·영업이익 기준)")
        rows = []
        for rank, l in enumerate(leaders, 1):
            rd = real_map.get(l.code)
            sig = rd.market_signals if rd else None
            fin = rd.financials if rd else None
            rows.append({
                "순위": rank,
                "종목": f"{l.name} ({l.code})",
                "대장주점수": l.total,
                "매출(억)": round(l.revenue / 1e8) if l.revenue else 0,
                "영업이익(억)": round(l.op_income / 1e8) if l.op_income else 0,
                "영익률%": fin.op_margin if fin else 0,
                "매출성장%": fin.revenue_growth_yoy if fin else 0,
                "PER": round(sig.per, 1) if sig and sig.per else None,
                "1년%": sig.price_return_1y if sig else 0,
            })
        df = pd.DataFrame(rows).set_index("순위")
        st.dataframe(df, use_container_width=True)

        # 성장성 vs 밸류 산점도 (저평가·고성장 탐지)
        st.markdown("### 📈 성장성 vs 밸류에이션")
        st.caption("오른쪽 아래 = 고성장인데 PER 낮음(저평가 후보). "
                   "왼쪽 위 = 저성장인데 비쌈.")
        sc = []
        for l in leaders:
            rd = real_map.get(l.code)
            if not rd or not rd.market_signals.per:
                continue
            sc.append({"종목": l.name,
                       "매출성장%": rd.financials.revenue_growth_yoy,
                       "PER": rd.market_signals.per})
        if sc:
            sdf = pd.DataFrame(sc)
            try:
                import altair as alt
                base = alt.Chart(sdf).encode(
                    x=alt.X("매출성장%:Q"),
                    y=alt.Y("PER:Q"),
                    tooltip=["종목", "매출성장%", "PER"])
                chart = base.mark_circle(size=180) + base.mark_text(
                    dy=-12, fontSize=11).encode(text="종목")
                st.altair_chart(chart, use_container_width=True)
            except Exception:
                st.scatter_chart(sdf, x="매출성장%", y="PER")
        else:
            st.caption("PER 데이터가 있는 종목이 부족해 산점도를 그리지 못했습니다.")

        st.info("이 업종을 곡괭이·공급관계까지 깊이 보려면 "
                "'🛠️ 섹터 편집'에서 구조를 정의한 뒤 심층 분석을 사용하세요.", icon="💡")


# ════════════════════════════════════════════════════════════════════════
# 🔬 심층 분석 — 사용자 정의 섹터 (곡괭이·공급관계 포함)
# ════════════════════════════════════════════════════════════════════════
else:
    st.subheader("🔬 심층 분석")
    sectors = list_sectors()
    if not sectors:
        st.warning("저장된 섹터가 없습니다. '🛠️ 섹터 편집'에서 먼저 구조를 정의하세요.")
        st.stop()

    sector = st.selectbox("내 섹터", sectors)
    data = load_sector(sector)
    vc = build_chain(data)
    companies = data["companies"]
    if not companies:
        st.warning("이 섹터에 종목이 없습니다. 섹터 편집에서 추가하세요.")
        st.stop()

    codes = tuple(str(c["code"]) for c in companies)
    with st.spinner(f"{sector} {len(codes)}종목 시세·재무 조회 중..."):
        real_map = _fetch_real(codes)
    st.caption(f"자동 조회 {len(real_map)}/{len(codes)}종목 (Yahoo Finance) · "
               f"구조 정보: 사용자 정의")

    det = ShovelDetector(vc)
    clf = MaturityClassifier()
    fin_map = {c: rd.financials for c, rd in real_map.items()}
    shovel_scores = {s.code: s for s in det.rank(fin_map)}
    leaders = rank_leaders(companies, real_map)
    name_by_code = {str(c["code"]): c["name"] for c in companies}

    st.divider()
    tab1, tab2, tab3, tab4 = st.tabs([
        "🧩 기능블록 지도", "👑 대장주 랭킹", "⛏️ 곡괭이 4분면", "🔗 공급관계",
    ])

    # 1. 기능블록 지도
    with tab1:
        st.caption("산업을 기능 부품 블록으로 쪼개고 블록별 지배 기업을 봅니다.")
        blocks = data.get("functional_blocks", [])
        if not blocks:
            st.info("정의된 기능블록이 없습니다. 섹터 편집에서 추가하세요.")
        else:
            leader_score = {l.code: l.total for l in leaders}
            for blk in blocks:
                members = [c for c in companies if blk in c.get("functional_blocks", [])]
                if not members:
                    continue
                members.sort(key=lambda c: leader_score.get(str(c["code"]), 0),
                             reverse=True)
                with st.container(border=True):
                    st.markdown(f"### 🧩 {blk}")
                    for rank, c in enumerate(members, 1):
                        code = str(c["code"])
                        sh = shovel_scores.get(code)
                        crown = "👑 " if rank == 1 else ""
                        final = "🏁완성품" if c.get("is_final_product") else "🔧부품"
                        shovel_txt = f"곡괭이 {sh.total:.2f}" if sh else "곡괭이 -"
                        st.write(f"{crown}**{c['name']}** ({code}) {final} · {shovel_txt}")

    # 2. 대장주 랭킹
    with tab2:
        st.caption("0.35×매출 + 0.35×영업이익 + 0.30×점유율 (섹터 내 정규화).")
        if leaders:
            import pandas as pd
            rows = []
            for rank, l in enumerate(leaders, 1):
                rows.append({
                    "순위": rank, "종목": f"{l.name} ({l.code})",
                    "대장주점수": l.total,
                    "매출(억)": round(l.revenue / 1e8) if l.revenue else 0,
                    "영업이익(억)": round(l.op_income / 1e8) if l.op_income else 0,
                    "점유율%": round(l.market_share * 100, 1),
                })
            df = pd.DataFrame(rows).set_index("순위")
            st.dataframe(df, use_container_width=True)
            st.bar_chart(df.set_index("종목")["대장주점수"], height=240)
            if not any(l.market_share for l in leaders):
                st.caption("※ 점유율 미입력 → 매출·영익 0.5/0.5 재정규화. "
                           "섹터 편집에서 점유율 입력 시 더 정확.")

    # 3. 곡괭이 4분면
    with tab3:
        st.caption("X=곡괭이(구조 중요도), Y=시장인식도(이미 비싼가). "
                   "오른쪽 아래 = 숨은 곡괭이 ★")
        import pandas as pd
        pts = []
        for code, sh in shovel_scores.items():
            rd = real_map.get(code)
            if not rd:
                continue
            cls = clf.classify(sh, rd.market_signals)
            pts.append({"종목": name_by_code.get(code, code),
                        "곡괭이점수": sh.total, "시장인식도": cls.recognition,
                        "분면": cls.quadrant})
        if pts:
            df = pd.DataFrame(pts)
            try:
                import altair as alt
                base = alt.Chart(df).encode(
                    x=alt.X("곡괭이점수:Q", scale=alt.Scale(domain=[0, 1])),
                    y=alt.Y("시장인식도:Q", scale=alt.Scale(domain=[0, 1])),
                    color="분면:N",
                    tooltip=["종목", "곡괭이점수", "시장인식도", "분면"])
                chart = base.mark_circle(size=200) + base.mark_text(
                    dy=-12, fontSize=11).encode(text="종목")
                st.altair_chart(chart, use_container_width=True)
            except Exception:
                st.scatter_chart(df, x="곡괭이점수", y="시장인식도")
            hidden = df[df["분면"] == "숨은곡괭이"]
            if not hidden.empty:
                st.markdown("**★ 숨은 곡괭이 후보**")
                for _, r in hidden.iterrows():
                    st.write(f"- {r['종목']} (곡괭이 {r['곡괭이점수']:.2f} / "
                             f"인식도 {r['시장인식도']:.2f})")
        else:
            st.info("데이터 없음.")

    # 4. 공급관계
    with tab4:
        st.caption("화살표 A→B = A가 B에 납품. 숫자는 의존도.")
        rels = data.get("supply_relations", [])
        if not rels:
            st.info("등록된 공급관계가 없습니다. 섹터 편집에서 추가하세요.")
        else:
            lines = ["digraph G {", "rankdir=LR;",
                     'node [shape=box, style="rounded,filled", fontname="sans"];']
            for c in companies:
                code = str(c["code"])
                color = "#ffe0b2" if c.get("is_final_product") else "#c8e6c9"
                lines.append(f'"{code}" [label="{c["name"]}", fillcolor="{color}"];')
            for r in rels:
                lines.append(f'"{r["from"]}" -> "{r["to"]}" '
                             f'[label="{r.get("part","")} {r.get("dependency",0):.2f}", '
                             f'fontsize=10];')
            lines.append("}")
            st.graphviz_chart("\n".join(lines), use_container_width=True)
            st.caption("🟧 완성품(금 캐는 사람)  🟩 부품·소재(곡괭이 후보)")
