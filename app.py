"""
ValueChain V3 — 섹터 종목 연결 구조 분석 (메인).

"섹터를 선택하면, 그 산업의 종목들이 서로 어떻게 엮여 있는지
(누가 누구에게 무엇을 공급하는지)를 구조로 보여준다."

예측 아님. 곡괭이 점수 같은 판정 없음. 구조 그 자체를 본다.
투자 자문 아님.

  🔬 연결 분석 — 사용자가 정의한 섹터의 종목 연결도 (공급관계 + 기능블록)
  🚀 업종 둘러보기 — 거래소 전체 업종의 구성 종목·재무 (구조 정의 전 탐색용)

시세·재무는 yfinance 자동. 연결 구조는 '🛠️ 섹터 편집'에서 정의.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(page_title="ValueChain 연결 분석",
                   page_icon="🔗", layout="centered")

from data.sector_store import list_sectors, load_sector, build_chain
from data.market_sectors import get_industries, stocks_in_industry
from data.realdata import YfinanceDataProvider
from analysis.leader import rank_leaders


@st.cache_data(ttl=3600)
def _industries():
    return get_industries()


@st.cache_data(ttl=3600)
def _stocks(industry: str):
    return stocks_in_industry(industry)


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_real(codes: tuple):
    return YfinanceDataProvider().fetch_many(list(codes))


st.title("🔗 ValueChain 연결 분석")
st.caption("섹터 종목들이 서로 어떻게 엮여 있는지(공급 구조)를 봅니다. "
           "예측·판정 아님 · 구조 이해 · 투자 자문 아님.")

mode = st.radio("모드", ["🔬 연결 분석 (내 섹터)", "🚀 업종 둘러보기 (전체)"],
                horizontal=True)
st.divider()


# ════════════════════════════════════════════════════════════════════════
# 🔬 연결 분석 — 사용자 정의 섹터의 종목 연결 구조
# ════════════════════════════════════════════════════════════════════════
if mode == "🔬 연결 분석 (내 섹터)":
    sectors = list_sectors()
    if not sectors:
        st.warning("저장된 섹터가 없습니다. '🛠️ 섹터 편집'에서 종목과 연결관계를 먼저 정의하세요.")
        st.stop()

    sector = st.selectbox("섹터 선택", sectors)
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
               f"연결 구조: 사용자 정의")

    name_by_code = {str(c["code"]): c["name"] for c in companies}
    rels = data.get("supply_relations", [])

    st.divider()
    tab_graph, tab_block, tab_detail, tab_size = st.tabs([
        "🔗 연결도", "🧩 기능블록", "🔎 종목별 연결", "📊 규모·재무",
    ])

    # ── 연결도 (그래프) ──────────────────────────────────────────────────
    with tab_graph:
        st.caption("화살표 A→B = A가 B에 납품. 숫자는 의존도. "
                   "여러 곳에 연결된 종목일수록 산업의 길목.")
        if not rels:
            st.info("등록된 연결(공급관계)이 없습니다. 섹터 편집에서 추가하세요.")
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
            st.caption("🟧 완성품(최종 제품)  🟩 부품·소재·장비(공급단)")

    # ── 기능블록별 종목 ──────────────────────────────────────────────────
    with tab_block:
        st.caption("산업을 기능 부품 블록으로 쪼개고 블록마다 어떤 종목이 있는지 봅니다.")
        blocks = data.get("functional_blocks", [])
        if not blocks:
            st.info("정의된 기능블록이 없습니다. 섹터 편집에서 추가하세요.")
        else:
            for blk in blocks:
                members = [c for c in companies if blk in c.get("functional_blocks", [])]
                if not members:
                    continue
                with st.container(border=True):
                    st.markdown(f"### 🧩 {blk}")
                    for c in members:
                        final = "🏁완성품" if c.get("is_final_product") else "🔧부품"
                        st.write(f"- **{c['name']}** ({c['code']}) {final}")
            # 미분류 종목
            unclassified = [c for c in companies if not c.get("functional_blocks")]
            if unclassified:
                with st.container(border=True):
                    st.markdown("### ❓ 미분류")
                    for c in unclassified:
                        st.write(f"- {c['name']} ({c['code']})")

    # ── 종목별 연결 (상류/하류 텍스트) ──────────────────────────────────
    with tab_detail:
        st.caption("종목을 고르면 그 종목이 누구에게 납품하고(하류) "
                   "누구로부터 공급받는지(상류)를 봅니다.")
        sel_code = st.selectbox(
            "종목", codes,
            format_func=lambda x: f"{name_by_code.get(x, x)} ({x})")
        ups = vc.upstream_of(sel_code)     # 이 종목에 납품하는 공급사
        downs = vc.downstream_of(sel_code) # 이 종목이 납품하는 고객사

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**⬅️ 공급받음 (상류)**")
            if ups:
                for u in ups:
                    edge = vc.g.get_edge_data(u, sel_code)
                    st.write(f"- {name_by_code.get(u, u)} "
                             f"(의존도 {edge.get('weight', 0):.2f})")
            else:
                st.caption("등록된 상류 공급사 없음")
        with c2:
            st.markdown("**➡️ 납품함 (하류)**")
            if downs:
                for d in downs:
                    edge = vc.g.get_edge_data(sel_code, d)
                    st.write(f"- {name_by_code.get(d, d)} "
                             f"(의존도 {edge.get('weight', 0):.2f})")
            else:
                st.caption("등록된 하류 고객사 없음 (완성품일 가능성)")

        # 이 종목 관련 부품/품목
        parts = [r for r in rels
                 if str(r["from"]) == sel_code or str(r["to"]) == sel_code]
        if parts:
            st.markdown("**관련 품목**")
            for r in parts:
                fn = name_by_code.get(str(r["from"]), r["from"])
                tn = name_by_code.get(str(r["to"]), r["to"])
                st.write(f"- {fn} → {tn}: {r.get('part','')} "
                         f"[{r.get('block','')}]")

    # ── 규모·재무 ────────────────────────────────────────────────────────
    with tab_size:
        st.caption("연결 구조와 별개로, 각 종목의 규모·재무를 참고용으로 봅니다.")
        leaders = rank_leaders(companies, real_map)
        if leaders:
            import pandas as pd
            rows = []
            for rank, l in enumerate(leaders, 1):
                rd = real_map.get(l.code)
                fin = rd.financials if rd else None
                rows.append({
                    "순위": rank, "종목": f"{l.name} ({l.code})",
                    "매출(억)": round(l.revenue / 1e8) if l.revenue else 0,
                    "영업이익(억)": round(l.op_income / 1e8) if l.op_income else 0,
                    "영익률%": fin.op_margin if fin else 0,
                    "매출성장%": fin.revenue_growth_yoy if fin else 0,
                })
            st.dataframe(pd.DataFrame(rows).set_index("순위"),
                         use_container_width=True)
        else:
            st.info("재무 데이터 없음.")


# ════════════════════════════════════════════════════════════════════════
# 🚀 업종 둘러보기 — 전체 업종 구성 종목 탐색 (구조 정의 전)
# ════════════════════════════════════════════════════════════════════════
else:
    st.subheader("🚀 업종 둘러보기")
    st.caption("거래소 공식 업종을 골라 구성 종목과 재무를 봅니다. "
               "여기서 관심 종목을 파악한 뒤 '🛠️ 섹터 편집'에서 연결 구조를 정의하세요.")

    inds = _industries()
    industry = st.selectbox("업종", inds)
    top_n = st.slider("종목 수 (시총 상위)", 5, 30, 15)

    if st.button("종목 보기", type="primary", use_container_width=True):
        cand = _stocks(industry)
        if not cand:
            st.error("해당 업종 종목을 불러오지 못했습니다.")
            st.stop()
        picked = cand[:top_n]
        codes = tuple(str(s["code"]) for s in picked)
        with st.spinner(f"{industry} {len(codes)}종목 재무 조회 중..."):
            real_map = _fetch_real(codes)
        st.caption(f"자동 조회 {len(real_map)}/{len(codes)}종목 · Yahoo Finance")

        import pandas as pd
        rows = []
        for s in picked:
            code = str(s["code"])
            rd = real_map.get(code)
            fin = rd.financials if rd else None
            sig = rd.market_signals if rd else None
            rows.append({
                "종목": f"{s['name']} ({code})",
                "시장": s.get("market", ""),
                "매출(억)": round(fin.revenue / 1e8) if fin and fin.revenue else 0,
                "영익률%": fin.op_margin if fin else 0,
                "매출성장%": fin.revenue_growth_yoy if fin else 0,
                "PER": round(sig.per, 1) if sig and sig.per else None,
            })
        df = pd.DataFrame(rows)
        df = df.sort_values("매출(억)", ascending=False).reset_index(drop=True)
        st.dataframe(df, use_container_width=True)
        st.info("이 종목들이 서로 어떻게 엮이는지 보려면 "
                "'🛠️ 섹터 편집'에서 연결관계를 정의한 뒤 연결 분석을 사용하세요.",
                icon="💡")
