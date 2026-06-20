"""
ValueChain 주식 추천 플랫폼 - Streamlit 모바일 앱
실행: streamlit run app.py
"""
import sys
import os
import warnings
from datetime import datetime, timezone, timedelta
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

KST = timezone(timedelta(hours=9))

st.markdown("""
<style>
.buy   { color: #00c853; font-weight: bold; font-size: 1.15em; }
.hold  { color: #ffd600; font-weight: bold; font-size: 1.15em; }
.sell  { color: #ff1744; font-weight: bold; font-size: 1.15em; }
.avoid { color: #9e9e9e; font-weight: bold; font-size: 1.15em; }
.price-up   { color: #00c853; font-size: 1.4em; font-weight: bold; }
.price-down { color: #ff1744; font-size: 1.4em; font-weight: bold; }
.price-flat { color: #9e9e9e; font-size: 1.4em; font-weight: bold; }
.source-tag { color: #888; font-size: 0.75em; }
</style>
""", unsafe_allow_html=True)


# ── 자동 새로고침 (장중 60초마다) ────────────────────────────────────────
def _is_market_hours() -> bool:
    now = datetime.now(KST)
    return now.weekday() < 5 and 9 <= now.hour < 16

try:
    from streamlit_autorefresh import st_autorefresh
    if _is_market_hours():
        st_autorefresh(interval=60_000, key="market_refresh")
except ImportError:
    pass


# ── 실시간 가격 티커 ─────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_live_price(code: str):
    """현재가·등락률·거래량 (60초 캐시)."""
    import yfinance as yf
    for suffix in [".KS", ".KQ"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(f"{code}{suffix}")
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price:
            prev  = info.get("previousClose") or price
            chg   = price - prev
            chg_p = chg / prev * 100 if prev else 0
            vol   = info.get("volume") or 0
            fetched_at = datetime.now(KST).strftime("%H:%M:%S")
            return {
                "price": price, "chg": chg, "chg_p": chg_p,
                "volume": vol, "fetched_at": fetched_at,
                "source": "Yahoo Finance (15분 지연)",
            }
    return None


def render_price_ticker(code: str, name: str):
    """종목 상단 가격 티커 (주식창 스타일)."""
    data = fetch_live_price(code)
    if not data:
        return
    price = data["price"]
    chg   = data["chg"]
    chg_p = data["chg_p"]
    css   = "price-up" if chg > 0 else ("price-down" if chg < 0 else "price-flat")
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "-")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(
            f'<span class="{css}">{price:,.0f}원 '
            f'{arrow} {abs(chg):,.0f} ({chg_p:+.2f}%)</span>',
            unsafe_allow_html=True,
        )
    with col2:
        st.caption(f"거래량 {data['volume']:,}주")

    st.markdown(
        f'<span class="source-tag">출처: {data["source"]} | '
        f'수집: {data["fetched_at"]} KST</span>',
        unsafe_allow_html=True,
    )


# ── 다년도 재무 추이 차트 ────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_financials_history(code: str):
    """4년 치 매출·영업이익 데이터."""
    import yfinance as yf
    import pandas as pd
    for suffix in [".KS", ".KQ"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(f"{code}{suffix}")
        fin = t.financials
        if not fin.empty:
            rows = {}
            for label, key in [("매출(억)", "Total Revenue"),
                                ("영업이익(억)", "Operating Income")]:
                if key in fin.index:
                    s = fin.loc[key].dropna().sort_index()
                    rows[label] = (s / 1e8).round(0)
            if rows:
                df = pd.DataFrame(rows)
                df.index = df.index.strftime("%Y")
                return df, datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "Yahoo Finance"
    return None, None, None


@st.cache_data(ttl=60)
def fetch_price_history(code: str):
    """1년 주가 + 거래량 히스토리."""
    import yfinance as yf
    for suffix in [".KS", ".KQ"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(f"{code}{suffix}")
        hist = t.history(period="1y")
        if not hist.empty:
            return hist, datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "Yahoo Finance"
    return None, None, None


# ── 지표 탭 ─────────────────────────────────────────────────────────────
def _render_metrics_tab(v, real_data):
    f   = real_data.financials
    sig = real_data.market_signals
    m   = v.metrics

    # 주식창 스타일 가격 티커
    st.markdown("##### 현재 시세")
    render_price_ticker(v.code, v.name)
    st.divider()

    # 핵심 재무 지표
    st.markdown("##### 핵심 지표")
    c1, c2, c3 = st.columns(3)
    c1.metric("시가총액",    m["현재가"])
    c2.metric("PER",         f"{sig.per:.1f}배"  if sig.per  else "N/A")
    c3.metric("PBR",         f"{sig.pbr:.1f}배"  if sig.pbr  else "N/A")

    c4, c5, c6 = st.columns(3)
    c4.metric("매출성장(YoY)",  f"{f.revenue_growth_yoy:+.1f}%")
    c5.metric("영업이익 성장",  f"{f.op_profit_growth_yoy:+.1f}%")
    c6.metric("영익률",         f"{f.op_margin:.1f}%")

    st.markdown(
        '<span class="source-tag">출처: Yahoo Finance 연간 재무제표 | '
        f'기준: 최근 결산연도</span>',
        unsafe_allow_html=True,
    )
    st.divider()

    # 다년도 매출·영업이익 추이
    st.markdown("##### 매출 · 영업이익 추이 (연간)")
    df_fin, fin_time, fin_src = fetch_financials_history(v.code)
    if df_fin is not None and not df_fin.empty:
        st.bar_chart(df_fin, height=220)
        st.markdown(
            f'<span class="source-tag">출처: {fin_src} | 수집: {fin_time}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("재무 추이 데이터 없음")
    st.divider()

    # 주가 차트 + 거래량
    st.markdown("##### 주가 차트 (1년)")
    hist, price_time, price_src = fetch_price_history(v.code)
    if hist is not None:
        st.line_chart(hist["Close"], height=200)
        st.markdown("##### 거래량 (1년)")
        st.bar_chart(hist["Volume"], height=120)
        st.markdown(
            f'<span class="source-tag">출처: {price_src} (15분 지연) | '
            f'수집: {price_time}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("주가 데이터 없음")
    st.divider()

    # 판정 근거 전체
    st.markdown("##### 판정 근거")
    for r in v.reasons:
        st.write(f"• {r}")
    st.markdown(
        '<span class="source-tag">곡괭이점수: 밸류체인 그래프 구조 분석 | '
        '재무실체: Yahoo Finance 연간 재무제표</span>',
        unsafe_allow_html=True,
    )


# ── 뉴스 탭 ─────────────────────────────────────────────────────────────
def _render_news_tab(company_name: str):
    try:
        with st.spinner("뉴스 불러오는 중..."):
            news_items = fetch_stock_news(company_name, display=8)
        if not news_items:
            st.caption("관련 뉴스 없음")
            return

        fetched_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
        st.markdown(
            f'<span class="source-tag">출처: 네이버 뉴스 검색 API | '
            f'수집: {fetched_at} | 검색어: "{company_name} 주가"</span>',
            unsafe_allow_html=True,
        )
        st.divider()

        for item in news_items:
            st.markdown(f"**{item.title}**")
            if item.description:
                desc = item.description
                st.caption(desc[:120] + "..." if len(desc) > 120 else desc)
            if item.pub_date:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(item.pub_date)
                    st.caption(f"🕐 {dt.strftime('%Y-%m-%d %H:%M')}")
                except Exception:
                    st.caption(f"🕐 {item.pub_date[:16]}")
            if item.link:
                st.markdown(f"[기사 원문 →]({item.link})")
            st.divider()
    except Exception as e:
        st.warning(f"뉴스 로드 실패: {e}")


# ── 종목 카드 ────────────────────────────────────────────────────────────
def render_verdict_card(v, real_data, action_css: str, action_label: str):
    with st.container(border=True):
        # 헤더
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{v.name}**  `{v.code}`")
            st.caption(f"확신: {v.confidence}")
        with c2:
            st.markdown(f'<span class="{action_css}">{action_label}</span>',
                        unsafe_allow_html=True)

        # 핵심 수치 한 줄
        m = v.metrics
        cols = st.columns(4)
        cols[0].metric("매출성장",  m["매출성장"])
        cols[1].metric("영익률",    m["영업이익률"])
        cols[2].metric("PER",       m["PER"])
        cols[3].metric("1년수익률", m["1년수익률"])

        # 판정 요약
        st.info(v.reasons[-1], icon="💡")

        # 📊 지표 / 📰 뉴스 탭
        tab_metric, tab_news = st.tabs(["📊 지표 상세", "📰 관련 뉴스"])
        with tab_metric:
            _render_metrics_tab(v, real_data)
        with tab_news:
            _render_news_tab(v.name)


# ── 섹터 분석 실행 ───────────────────────────────────────────────────────
def run_analysis(sectors: list):
    for sector_name, headlines, heat in sectors:
        st.divider()
        c1, c2 = st.columns([3, 1])
        with c1:
            st.subheader(f"📊 {sector_name}")
        with c2:
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
        scores  = det.rank(fin_map)

        verdicts = []
        for s in scores:
            d = all_data.get(s.code)
            if not d:
                continue
            classified = clf.classify(s, d.market_signals)
            verdicts.append((make_verdict(classified, s, d.market_signals, d), d))

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

now_kst = datetime.now(KST)
market_status = "🟢 장중 (60초 자동 갱신)" if _is_market_hours() else "🔴 장 마감"
st.caption(f"{now_kst.strftime('%Y-%m-%d %H:%M KST')}  {market_status}")
st.caption("※ 투자 자문 아님. 후보 추리기 참고 자료.")

st.divider()
mode = st.radio("분석 방식", ["🔥 뉴스 기반 자동 감지", "📂 섹터 직접 선택"], horizontal=True)

if mode == "🔥 뉴스 기반 자동 감지":
    top_n = st.slider("분석할 섹터 수", 1, 4, 2)
    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        with st.spinner("뉴스 수집 중..."):
            hot = detect_hot_sectors(top_n=top_n)
        run_analysis([(h.sector, h.top_headlines, h.heat) for h in hot])
else:
    selected = st.selectbox("섹터 선택", list(SECTOR_QUERIES.keys()))
    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        run_analysis([(selected, [], 0)])
