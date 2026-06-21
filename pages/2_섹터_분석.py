"""
V3 STEP 3+4 — 섹터 분석 출력 화면.

저장된 섹터(JSON 구조) + yfinance(시세·재무 자동)를 결합해
산업 구조를 4개 시각으로 보여준다:
  1. 기능블록 지도   — 블록별 지배 기업
  2. 대장주 랭킹     — 매출+영익+점유율
  3. 곡괭이 4분면    — 숨은 보석 탐지
  4. 공급관계 그래프 — 누가 누구에게 납품하나

예측 아님. 현재 구조 이해. 투자 자문 아님.
"""
import sys
import os
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from data.sector_store import list_sectors, load_sector, build_chain
from data.realdata import YfinanceDataProvider
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier
from analysis.leader import rank_leaders

st.set_page_config(page_title="섹터 분석", page_icon="🔬", layout="centered")

st.title("🔬 섹터 분석")
st.caption("산업을 기능블록으로 해부하고 누가 어디를 쥐었는지 봅니다. "
           "예측 아님 · 구조 이해 · 투자 자문 아님.")


# ── 데이터 자동 연결 (STEP 3) ────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def fetch_real(codes: tuple):
    """yfinance 시세·재무 자동 수집 (10분 캐시). 실패 종목은 제외."""
    provider = YfinanceDataProvider()
    return provider.fetch_many(list(codes))


# ── 섹터 선택 ────────────────────────────────────────────────────────────
sectors = list_sectors()
if not sectors:
    st.warning("저장된 섹터가 없습니다. '🛠️ 섹터 편집'에서 먼저 만들어 주세요.")
    st.stop()

sector = st.selectbox("분석할 섹터", sectors)
data = load_sector(sector)
vc = build_chain(data)
companies = data["companies"]

if not companies:
    st.warning("이 섹터에 등록된 종목이 없습니다. 섹터 편집에서 종목을 추가하세요.")
    st.stop()

codes = tuple(str(c["code"]) for c in companies)
with st.spinner(f"{sector} 종목 {len(codes)}개의 시세·재무 조회 중..."):
    real_map = fetch_real(codes)

st.caption(f"자동 조회: {len(real_map)}/{len(codes)}종목 성공 "
           f"(출처: Yahoo Finance) · 구조 정보: 사용자 정의")

# 엔진 계산
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


# ── 1. 기능블록 지도 ─────────────────────────────────────────────────────
with tab1:
    st.subheader("기능블록 지도")
    st.caption("산업을 기능 부품 블록으로 쪼개고, 블록별로 어느 기업이 강한지 봅니다.")
    blocks = data.get("functional_blocks", [])
    if not blocks:
        st.info("정의된 기능블록이 없습니다. 섹터 편집에서 블록을 추가하세요.")
    else:
        leader_score = {l.code: l.total for l in leaders}
        for blk in blocks:
            members = [c for c in companies if blk in c.get("functional_blocks", [])]
            if not members:
                continue
            # 블록 내 대장주 점수 순
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


# ── 2. 대장주 랭킹 ───────────────────────────────────────────────────────
with tab2:
    st.subheader("대장주 랭킹")
    st.caption("0.35×매출 + 0.35×영업이익 + 0.30×점유율 (섹터 내 정규화). "
               "'지금 큰 기업' 순서.")
    if not leaders:
        st.info("데이터 없음.")
    else:
        import pandas as pd
        rows = []
        for rank, l in enumerate(leaders, 1):
            rows.append({
                "순위": rank,
                "종목": f"{l.name} ({l.code})",
                "대장주점수": l.total,
                "매출(억)": round(l.revenue / 1e8) if l.revenue else 0,
                "영업이익(억)": round(l.op_income / 1e8) if l.op_income else 0,
                "점유율%": round(l.market_share * 100, 1),
            })
        df = pd.DataFrame(rows).set_index("순위")
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index("종목")["대장주점수"], height=240)
        if not any(l.market_share for l in leaders):
            st.caption("※ 점유율 미입력 → 매출·영익 0.5/0.5로 재정규화됨. "
                       "섹터 편집에서 점유율을 넣으면 더 정확해집니다.")


# ── 3. 곡괭이 4분면 ──────────────────────────────────────────────────────
with tab3:
    st.subheader("곡괭이 4분면")
    st.caption("X=곡괭이 점수(구조적 중요도), Y=시장 인식도(이미 비싼가). "
               "오른쪽 아래 = 숨은 곡괭이 ★ (구조는 강한데 저평가)")
    import pandas as pd
    pts = []
    for code, sh in shovel_scores.items():
        rd = real_map.get(code)
        if not rd:
            continue
        cls = clf.classify(sh, rd.market_signals)
        pts.append({
            "종목": name_by_code.get(code, code),
            "곡괭이점수": sh.total,
            "시장인식도": cls.recognition,
            "분면": cls.quadrant,
        })
    if not pts:
        st.info("데이터 없음.")
    else:
        df = pd.DataFrame(pts)
        try:
            import altair as alt
            base = alt.Chart(df).encode(
                x=alt.X("곡괭이점수:Q", scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("시장인식도:Q", scale=alt.Scale(domain=[0, 1])),
                color="분면:N",
                tooltip=["종목", "곡괭이점수", "시장인식도", "분면"],
            )
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


# ── 4. 공급관계 그래프 ───────────────────────────────────────────────────
with tab4:
    st.subheader("공급관계 그래프")
    st.caption("화살표 A→B = A가 B에 납품. 숫자는 의존도. "
               "여러 곳에 납품하는 상류 = 곡괭이.")
    rels = data.get("supply_relations", [])
    if not rels:
        st.info("등록된 공급관계가 없습니다. 섹터 편집에서 추가하세요.")
    else:
        # graphviz DOT 문자열 (추가 의존성 없이 렌더)
        lines = ["digraph G {", 'rankdir=LR;',
                 'node [shape=box, style="rounded,filled", fontname="sans"];']
        for c in companies:
            code = str(c["code"])
            color = "#ffe0b2" if c.get("is_final_product") else "#c8e6c9"
            lines.append(f'"{code}" [label="{c["name"]}", fillcolor="{color}"];')
        for r in rels:
            frm, to = str(r["from"]), str(r["to"])
            part = r.get("part", "")
            dep = r.get("dependency", 0)
            lines.append(f'"{frm}" -> "{to}" '
                         f'[label="{part} {dep:.2f}", fontsize=10];')
        lines.append("}")
        st.graphviz_chart("\n".join(lines), use_container_width=True)
        st.caption("🟧 완성품(금 캐는 사람)  🟩 부품·소재(곡괭이 후보)")
