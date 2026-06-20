"""
ValueChain 주식 추천 플랫폼 - Streamlit 모바일 앱
실행: streamlit run app.py
"""
import sys
import os
sys.path.insert(0, ".")

import streamlit as st

st.set_page_config(
    page_title="ValueChain 추천",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Streamlit Cloud 시크릿 → 환경변수 로드
if hasattr(st, "secrets") and "NAVER_CLIENT_ID" in st.secrets:
    os.environ["NAVER_CLIENT_ID"] = st.secrets["NAVER_CLIENT_ID"]
    os.environ["NAVER_CLIENT_SECRET"] = st.secrets["NAVER_CLIENT_SECRET"]

from news.theme import detect_hot_sectors
from data.sectors import get_chain, SECTOR_QUERIES
from data.realdata import YfinanceDataProvider
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier
from analysis.verdict import make_verdict

# ── 스타일 ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
.buy  { color: #00c853; font-weight: bold; font-size: 1.1em; }
.hold { color: #ffd600; font-weight: bold; font-size: 1.1em; }
.sell { color: #ff1744; font-weight: bold; font-size: 1.1em; }
.avoid{ color: #9e9e9e; font-weight: bold; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)


def run_analysis(sectors: list):
    for sector_name, headlines, heat in sectors:
        st.divider()
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"📊 {sector_name}")
        with col2:
            if heat:
                st.metric("뉴스", f"{heat:,}건")

        if headlines:
            with st.expander("관련 뉴스"):
                for h in headlines[:3]:
                    st.write(f"• {h}")

        vc = get_chain(sector_name)
        if vc is None:
            st.warning("밸류체인 템플릿 없음")
            continue

        codes = list(vc.g.nodes())
        with st.spinner(f"{sector_name} 데이터 수집 중..."):
            provider = YfinanceDataProvider()
            all_data = provider.fetch_many(codes)

        if not all_data:
            st.error("데이터 수집 실패")
            continue

        det = ShovelDetector(vc)
        clf = MaturityClassifier()
        fin_map = {c: d.financials for c, d in all_data.items()}
        scores = det.rank(fin_map)

        verdicts = []
        for s in scores:
            d = all_data.get(s.code)
            if not d:
                continue
            classified = clf.classify(s, d.market_signals)
            v = make_verdict(classified, s, d.market_signals, d)
            verdicts.append(v)

        buy_list  = [v for v in verdicts if v.action == "BUY"]
        hold_list = [v for v in verdicts if v.action == "HOLD"]
        sell_list = [v for v in verdicts if v.action in ("SELL", "AVOID")]

        if buy_list:
            st.markdown("### ✅ BUY 추천")
            for v in buy_list:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{v.name}**  `{v.code}`")
                        st.caption(f"확신: {v.confidence}")
                    with c2:
                        st.markdown('<span class="buy">▲ BUY</span>', unsafe_allow_html=True)

                    m = v.metrics
                    cols = st.columns(4)
                    cols[0].metric("시가총액", m["현재가"])
                    cols[1].metric("매출성장", m["매출성장"])
                    cols[2].metric("영익률", m["영업이익률"])
                    cols[3].metric("PER", m["PER"])

                    cols2 = st.columns(3)
                    cols2[0].metric("1년수익률", m["1년수익률"])
                    cols2[1].metric("곡괭이점수", m["곡괭이점수"])
                    cols2[2].metric("4분면", m["4분면"])

                    with st.expander("판정 근거 보기"):
                        for r in v.reasons:
                            st.write(r)

        if hold_list:
            st.markdown("### ➖ HOLD")
            for v in hold_list:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{v.name}**")
                        m = v.metrics
                        st.caption(
                            f"매출 {m['매출성장']} | 영익률 {m['영업이익률']} "
                            f"| PER {m['PER']} | 1년 {m['1년수익률']}"
                        )
                    with c2:
                        st.markdown('<span class="hold">- HOLD</span>', unsafe_allow_html=True)
                    with st.expander("근거"):
                        st.write(v.reasons[-1])

        if sell_list:
            st.markdown("### ❌ SELL / AVOID")
            for v in sell_list:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{v.name}**")
                        st.caption(v.reasons[-1])
                    with c2:
                        label = "▼ SELL" if v.action == "SELL" else "× AVOID"
                        css = "sell" if v.action == "SELL" else "avoid"
                        st.markdown(f'<span class="{css}">{label}</span>',
                                    unsafe_allow_html=True)


# ── 메인 UI ─────────────────────────────────────────────────────────────
st.title("📈 ValueChain 주식 추천")
st.caption("뉴스 기반 핫 섹터 → 밸류체인 분석 → BUY/HOLD/SELL")
st.caption("※ 투자 자문 아님. 후보 추리기 참고 자료.")

st.divider()
mode = st.radio("분석 방식", ["🔥 뉴스 기반 자동 감지", "📂 섹터 직접 선택"], horizontal=True)

if mode == "🔥 뉴스 기반 자동 감지":
    top_n = st.slider("분석할 섹터 수", 1, 4, 2)
    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        with st.spinner("뉴스 수집 중..."):
            hot = detect_hot_sectors(top_n=top_n)
        sectors_to_run = [(h.sector, h.top_headlines, h.heat) for h in hot]
        run_analysis(sectors_to_run)
else:
    available = list(SECTOR_QUERIES.keys())
    selected = st.selectbox("섹터 선택", available)
    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        run_analysis([(selected, [], 0)])
