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

from news.theme import detect_hot_sectors, SECTOR_QUERIES
from news.collector import fetch_stock_news
from data.sectors import get_chain
from data.realdata import YfinanceDataProvider
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier
from analysis.verdict import make_verdict

st.markdown("""
<style>
.buy  { color: #00c853; font-weight: bold; font-size: 1.1em; }
.hold { color: #ffd600; font-weight: bold; font-size: 1.1em; }
.sell { color: #ff1744; font-weight: bold; font-size: 1.1em; }
.avoid{ color: #9e9e9e; font-weight: bold; font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)


# ── 종목 카드 렌더링 ────────────────────────────────────────────────────
def render_verdict_card(v, real_data, action_css: str, action_label: str):
    """BUY/HOLD/SELL 종목 카드 — 지표·뉴스 탭 포함."""
    with st.container(border=True):
        # 헤더
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{v.name}**  `{v.code}`")
            st.caption(f"확신: {v.confidence}")
        with c2:
            st.markdown(f'<span class="{action_css}">{action_label}</span>',
                        unsafe_allow_html=True)

        # 핵심 수치 한 줄 요약
        m = v.metrics
        cols = st.columns(4)
        cols[0].metric("매출성장", m["매출성장"])
        cols[1].metric("영익률",   m["영업이익률"])
        cols[2].metric("PER",      m["PER"])
        cols[3].metric("1년수익률", m["1년수익률"])

        # 판정 근거 한 줄
        st.info(v.reasons[-1], icon="💡")

        # 탭: 지표 / 뉴스
        tab_metric, tab_news = st.tabs(["📊 지표", "📰 뉴스"])

        with tab_metric:
            _render_metrics_tab(v, real_data)

        with tab_news:
            _render_news_tab(v.name)


def _render_metrics_tab(v, real_data):
    """상세 재무 지표 + 주가 차트."""
    m = v.metrics
    f = real_data.financials
    sig = real_data.market_signals

    # 주요 지표 표
    st.markdown("**재무 지표**")
    col1, col2, col3 = st.columns(3)
    col1.metric("시가총액",   m["현재가"])
    col2.metric("곡괭이점수", m["곡괭이점수"])
    col3.metric("4분면",      m["4분면"])

    col4, col5, col6 = st.columns(3)
    col4.metric("매출성장(YoY)", f"{f.revenue_growth_yoy:+.1f}%")
    col5.metric("영업이익 성장", f"{f.op_profit_growth_yoy:+.1f}%")
    col6.metric("영익률",        f"{f.op_margin:.1f}%")

    col7, col8 = st.columns(2)
    col7.metric("PER",  f"{sig.per:.1f}배" if sig.per else "N/A")
    col8.metric("PBR",  f"{sig.pbr:.1f}배" if sig.pbr else "N/A")

    # 판정 근거 전체
    st.markdown("**판정 근거**")
    for r in v.reasons:
        st.write(f"• {r}")

    # 주가 차트 (1년)
    st.markdown("**주가 차트 (1년)**")
    try:
        import yfinance as yf
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for suffix in [".KS", ".KQ"]:
                ticker = yf.Ticker(f"{v.code}{suffix}")
                hist = ticker.history(period="1y")
                if not hist.empty:
                    break
        if not hist.empty:
            st.line_chart(hist["Close"], height=200)
        else:
            st.caption("차트 데이터 없음")
    except Exception as e:
        st.caption(f"차트 로드 실패: {e}")


def _render_news_tab(company_name: str):
    """종목 관련 최신 뉴스."""
    try:
        with st.spinner("뉴스 불러오는 중..."):
            news_items = fetch_stock_news(company_name, display=8)
        if not news_items:
            st.caption("관련 뉴스 없음")
            return
        for item in news_items:
            with st.container():
                st.markdown(f"**{item.title}**")
                if item.description:
                    st.caption(item.description[:100] + "..." if len(item.description) > 100 else item.description)
                if item.pub_date:
                    # pubDate 파싱: "Mon, 23 Jun 2025 10:30:00 +0900"
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(item.pub_date)
                        st.caption(f"🕐 {dt.strftime('%Y-%m-%d %H:%M')}")
                    except Exception:
                        st.caption(f"🕐 {item.pub_date[:16]}")
                if item.link:
                    st.markdown(f"[기사 원문 보기]({item.link})")
                st.divider()
    except Exception as e:
        st.warning(f"뉴스 로드 실패: {e}")


# ── 섹터 분석 실행 ───────────────────────────────────────────────────────
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
            with st.expander("관련 뉴스 헤드라인"):
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
            verdicts.append((v, d))

        buy_list  = [(v, d) for v, d in verdicts if v.action == "BUY"]
        hold_list = [(v, d) for v, d in verdicts if v.action == "HOLD"]
        sell_list = [(v, d) for v, d in verdicts if v.action in ("SELL", "AVOID")]

        if buy_list:
            st.markdown("### ✅ BUY 추천")
            for v, d in buy_list:
                render_verdict_card(v, d, "buy", "▲ BUY")

        if hold_list:
            st.markdown("### ➖ HOLD")
            for v, d in hold_list:
                render_verdict_card(v, d, "hold", "- HOLD")

        if sell_list:
            st.markdown("### ❌ SELL / AVOID")
            for v, d in sell_list:
                label = "▼ SELL" if v.action == "SELL" else "× AVOID"
                css   = "sell"  if v.action == "SELL" else "avoid"
                render_verdict_card(v, d, css, label)


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
