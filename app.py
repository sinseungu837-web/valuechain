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


# ── 접근 잠금 (본인 전용) ────────────────────────────────────────────────
def _check_password() -> bool:
    """
    APP_PASSWORD 시크릿이 설정돼 있으면 비밀번호를 요구한다.
    설정 안 돼 있으면(로컬 개발 등) 잠금 없이 통과.
    공유·상용화 전까지 본인만 사용하기 위한 최소 보호 장치.
    """
    expected = None
    if hasattr(st, "secrets") and "APP_PASSWORD" in st.secrets:
        expected = st.secrets["APP_PASSWORD"]
    if not expected:                       # 비번 미설정 → 잠금 해제
        return True
    if st.session_state.get("auth_ok"):    # 이미 인증됨
        return True

    st.title("🔒 ValueChain")
    st.caption("본인 전용 앱입니다. 비밀번호를 입력하세요.")
    pw = st.text_input("비밀번호", type="password")
    if st.button("입장", use_container_width=True):
        if pw == expected:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    return False


if not _check_password():
    st.stop()

from news.theme import detect_hot_sectors, detect_hot_and_stable, SECTOR_QUERIES
from news.collector import fetch_stock_news, search_news
from data.sectors import get_chain
from data.realdata import YfinanceDataProvider
from data.etf import SECTOR_ETFS, STOCK_ETFS, EtfInfo
from data.commodities import (fetch_commodity_prices, fetch_index_prices,
                               COMMODITY_INFO)
from analysis.shovel import ShovelDetector
from analysis.maturity import MaturityClassifier
from analysis.verdict import make_verdict
from analysis.scenario import SCENARIOS

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


# ── 실시간(당일 분봉) 차트 ───────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_intraday(code: str):
    """당일 1분봉 시세 (장중 실시간 추이용, 60초 캐시)."""
    import yfinance as yf
    for suffix in [".KS", ".KQ"]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(f"{code}{suffix}")
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            return hist, datetime.now(KST).strftime("%H:%M:%S KST")
    return None, None


def render_intraday_chart(code: str, name: str):
    """장중 실시간 분봉 차트. st_autorefresh로 자동 갱신됨."""
    hist, fetched = fetch_intraday(code)
    if hist is None or hist.empty:
        st.caption("당일 분봉 데이터 없음 (장 시작 전이거나 거래 없음)")
        return
    closes = hist["Close"]
    cur   = closes.iloc[-1]
    first = closes.iloc[0]
    chg_p = (cur - first) / first * 100 if first else 0
    css   = "price-up" if chg_p > 0 else ("price-down" if chg_p < 0 else "price-flat")
    arrow = "▲" if chg_p > 0 else ("▼" if chg_p < 0 else "-")

    st.markdown(
        f'<span class="{css}">당일 {arrow} {chg_p:+.2f}% '
        f'(시가 대비)</span>',
        unsafe_allow_html=True,
    )
    st.line_chart(closes, height=180)
    refresh_note = " · 60초 자동 갱신" if _is_market_hours() else ""
    st.markdown(
        f'<span class="source-tag">출처: Yahoo Finance 1분봉 | '
        f'갱신: {fetched}{refresh_note}</span>',
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

    # 실시간 당일 분봉 차트 (장중 자동 갱신)
    st.markdown("##### 실시간 차트 (당일)")
    render_intraday_chart(v.code, v.name)
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


# ── 증시 지수·환율 위젯 (상단 자동 표시) ─────────────────────────────────
@st.cache_data(ttl=120)
def _get_index_prices():
    return fetch_index_prices()


@st.cache_data(ttl=300)
def fetch_index_history(symbol: str, period: str = "1mo", interval: str = "1d"):
    """지수/환율 심볼의 히스토리 (팝오버 차트용)."""
    import yfinance as yf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = yf.Ticker(symbol)
    hist = t.history(period=period, interval=interval)
    if hist.empty:
        return None
    return hist["Close"]


def _render_index_popover_chart(p):
    """팝오버 안: 기간 선택 + 차트."""
    st.markdown(f"### {p.name}")
    val = f"{p.price:,.1f}" if p.unit == "pt" else f"{p.price:,.0f}"
    arrow = "▲" if p.chg_pct > 0 else ("▼" if p.chg_pct < 0 else "-")
    css = "price-up" if p.chg_pct > 0 else ("price-down" if p.chg_pct < 0 else "price-flat")
    st.markdown(
        f'<span class="{css}">{val} {p.unit} {arrow} {p.chg_pct:+.2f}%</span>',
        unsafe_allow_html=True,
    )

    period_label = st.radio(
        "기간", ["1일", "1개월", "1년"], horizontal=True,
        key=f"idx_period_{p.symbol}",
    )
    cfg = {"1일": ("1d", "5m"), "1개월": ("1mo", "1d"), "1년": ("1y", "1wk")}
    period, interval = cfg[period_label]

    closes = fetch_index_history(p.symbol, period=period, interval=interval)
    if closes is None or closes.empty:
        st.caption("차트 데이터 없음")
    else:
        st.line_chart(closes, height=240)
    st.caption("출처: Yahoo Finance (지연 시세)")


def render_index_bar():
    """코스피·코스닥·나스닥·S&P500·환율 2×3 그리드. 클릭 시 차트 팝오버."""
    indices = _get_index_prices()
    if not indices:
        return

    # 3개씩 2줄로 배치
    for row_start in range(0, len(indices), 3):
        row = indices[row_start:row_start + 3]
        cols = st.columns(3)
        for col, p in zip(cols, row):
            with col:
                if p.price > 0:
                    arrow = "▲" if p.chg_pct > 0 else ("▼" if p.chg_pct < 0 else "")
                    val = f"{p.price:,.1f}" if p.unit == "pt" else f"{p.price:,.0f}"
                    delta_css = "normal" if p.chg_pct >= 0 else "inverse"
                    st.metric(p.name, val, f"{arrow}{p.chg_pct:+.2f}%")
                    # 클릭하면 차트 팝오버
                    with st.popover("📈 차트 보기", use_container_width=True):
                        _render_index_popover_chart(p)
                else:
                    st.metric(p.name, "조회실패")

    st.caption(f"출처: Yahoo Finance (지연) | 수집: {indices[0].fetched_at} | 2분마다 갱신")


# ── 광물·원자재 가격 위젯 ────────────────────────────────────────────────
@st.cache_data(ttl=300)
def _get_commodity_prices():
    return fetch_commodity_prices()


def render_commodity_widget():
    with st.expander("🪨 원자재·광물 실시간 가격", expanded=False):
        st.caption("출처: Yahoo Finance | 15분 지연 | 가격은 USD, 괄호는 원화 환산")
        prices = _get_commodity_prices()
        if not prices:
            st.caption("데이터 없음")
            return
        cols = st.columns(3)
        for i, p in enumerate(prices):
            with cols[i % 3]:
                st.markdown(f"**{p.name}**")
                if p.price > 0:
                    color = "buy" if p.chg_pct > 0 else ("sell" if p.chg_pct < 0 else "")
                    arrow = "▲" if p.chg_pct > 0 else ("▼" if p.chg_pct < 0 else "-")
                    if color:
                        st.markdown(
                            f'<span class="{color}">{p.price:,.2f} {p.unit} '
                            f'{arrow}{abs(p.chg_pct):.2f}%</span>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.write(f"{p.price:,.2f} {p.unit}")
                    # 원화 환산 (USD/KRW 자체는 제외)
                    if p.price_krw and p.name != "USD/KRW":
                        krw_unit = p.unit.replace("USD", "원")
                        st.caption(f"≈ {p.price_krw:,.0f} {krw_unit}")
                    # 설명 버튼
                    info = COMMODITY_INFO.get(p.name)
                    if info:
                        with st.popover("ℹ️ 설명", use_container_width=True):
                            st.markdown(f"#### {p.name}")
                            st.markdown(info)
                else:
                    st.caption("조회 실패")
        st.caption(f"수집: {prices[0].fetched_at if prices else '-'}  "
                   f"※ 원화 환산은 현재 USD/KRW 환율 기준 참고치")


# ── 세상 상황 → 수혜 섹터 시나리오 ───────────────────────────────────────
@st.cache_data(ttl=120)
def _indicator_lookup():
    """현재 지수·원자재 값을 이름→(값,등락%) dict로."""
    out = {}
    for p in fetch_index_prices() + fetch_commodity_prices():
        out[p.name] = (p.price, p.chg_pct, p.unit)
    return out


@st.cache_data(ttl=1800)
def _scenario_news(query: str):
    try:
        return search_news(query, display=4)
    except Exception:
        return []


def render_scenario_widget():
    """거시 상황별 수혜/피해 섹터 + 현재 지표 + 관련 뉴스."""
    with st.expander("🌍 세상 상황별 수혜 섹터 (시나리오 분석)", expanded=False):
        st.caption("거시 상황이 바뀌면 어디가 뜨는지 — 과거 인과 패턴 기반 참고 자료. "
                   "예측이 아님.")
        titles = [s.title for s in SCENARIOS]
        picked = st.selectbox("상황 선택", titles, key="scenario_pick")
        sc = next((s for s in SCENARIOS if s.title == picked), None)
        if sc is None:
            return

        st.info(sc.summary)

        # 현재 관련 경제지표 실시간 표시
        ind = _indicator_lookup()
        watch = [n for n in sc.watch_indicators if n in ind]
        if watch:
            st.markdown("**📊 지금 확인할 지표**")
            cols = st.columns(len(watch))
            for col, name in zip(cols, watch):
                price, chg, unit = ind[name]
                arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "")
                val = f"{price:,.1f}" if unit == "pt" else f"{price:,.2f}"
                col.metric(name, val, f"{arrow}{chg:+.2f}%")

        # 수혜 / 피해 섹터
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🟢 수혜 섹터**")
            for sector, why in sc.winners:
                st.markdown(f"- **{sector}** — {why}")
        with c2:
            st.markdown("**🔴 부담 섹터**")
            if sc.losers:
                for sector, why in sc.losers:
                    st.markdown(f"- **{sector}** — {why}")
            else:
                st.caption("뚜렷한 피해 섹터 없음")

        st.caption("→ '섹터 직접 선택'에서 위 섹터를 골라 종목 단위로 분석할 수 있어요.")

        # 관련 뉴스
        st.divider()
        st.markdown("**📰 관련 최신 뉴스**")
        news = _scenario_news(sc.news_query)
        if not news:
            st.caption("관련 뉴스 없음")
        else:
            for it in news:
                st.markdown(f"- [{it.title}]({it.link})" if it.link
                            else f"- {it.title}")
            st.caption(f'출처: 네이버 뉴스 | 검색어: "{sc.news_query}"')


# ── 수주·계약 분석 탭 ────────────────────────────────────────────────────
BIZ_MODEL_DESC = {
    "B2B수주": ("🏗️ B2B 수주형", "프로젝트/계약 기반 매출. 수주잔고로 미래 매출 예측 가능"),
    "B2B납품": ("🔩 B2B 납품형", "기업 간 정기 납품 계약. 고객사 성장에 연동"),
    "B2C":     ("🛒 B2C 소비자형", "소비자 직접 판매. 브랜드·경기 민감"),
    "혼합":    ("🔀 혼합형", "B2B+B2C 또는 시장가 판매 혼재"),
}

@st.cache_data(ttl=1800)
def _fetch_contract_news(company_name: str, biz_model: str) -> list:
    """수주/계약 관련 뉴스 검색."""
    if biz_model in ("B2B수주", "B2B납품"):
        queries = [f"{company_name} 수주", f"{company_name} 계약 체결"]
    else:
        queries = [f"{company_name} 실적", f"{company_name} 매출"]
    items = []
    for q in queries:
        try:
            got = search_news(q, display=4)
            items.extend(got)
        except Exception:
            pass
    seen = set()
    unique = []
    for it in items:
        if it.title not in seen:
            seen.add(it.title)
            unique.append(it)
    return unique[:8]


def _render_contract_tab(code: str, name: str, biz_model: str):
    """수주·계약 분석 탭."""
    label, desc = BIZ_MODEL_DESC.get(biz_model, ("❓ 미분류", ""))

    st.markdown(f"### {label}")
    st.info(desc, icon="ℹ️")

    # 수익 구조 설명
    if biz_model == "B2B수주":
        st.markdown("""
**수주형 기업 체크리스트**
- ✅ 수주잔고(Order Backlog) 규모 → 확정 미래 매출
- ✅ 수주 취소율 → 리스크 지표
- ✅ 신규 수주 증가율 → 성장 신호
- ⚠️ 수주 집중도 → 특정 고객 과의존 리스크
""")
    elif biz_model == "B2B납품":
        st.markdown("""
**납품형 기업 체크리스트**
- ✅ 장기 공급 계약 체결 여부
- ✅ 고객사 다변화 (특정사 집중 리스크)
- ✅ 단가 협상력 (소재→완성품 전가 가능 여부)
- ⚠️ 재고 리스크 → 고객사 재고 조정 시 납품 감소
""")
    elif biz_model == "B2C":
        st.markdown("""
**소비자형 기업 체크리스트**
- ✅ 브랜드 인지도 / 재구매율
- ✅ MAU·WAU 등 사용자 지표 (게임·플랫폼)
- ✅ 경기 민감도 → 경기방어주 여부
- ⚠️ 경쟁 심화 → 마케팅비 증가 여부
""")
    else:
        st.markdown("""
**혼합형 기업 체크리스트**
- ✅ 수익원 분산 구조 확인
- ✅ 시장가 연동 비율 (원자재·철강 등)
- ✅ 자회사/사업부별 기여도
""")

    st.divider()
    st.markdown("##### 최근 수주·계약 뉴스")
    with st.spinner("계약·수주 뉴스 검색 중..."):
        news_items = _fetch_contract_news(name, biz_model)

    if not news_items:
        st.caption("관련 뉴스 없음")
        return

    fetched_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    st.markdown(
        f'<span class="source-tag">출처: 네이버 뉴스 | 수집: {fetched_at}</span>',
        unsafe_allow_html=True,
    )
    for item in news_items:
        st.markdown(f"**{item.title}**")
        if item.description:
            st.caption(item.description[:100] + "..." if len(item.description) > 100 else item.description)
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


# ── ETF 성능 조회 ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_etf_performance(code: str) -> dict:
    """ETF 현재가·1년수익률·시가총액 조회."""
    import yfinance as yf
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(f"{code}.KS")
        info = t.info
        price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        market_cap = info.get("marketCap") or 0

        hist = t.history(period="1y")
        ret_1y = 0.0
        if len(hist) >= 2:
            ret_1y = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100

        return {
            "price": price,
            "ret_1y": round(ret_1y, 1),
            "market_cap": market_cap,
            "ok": price > 0,
        }
    except Exception:
        return {"price": 0, "ret_1y": 0, "market_cap": 0, "ok": False}


def _render_etf_tab(code: str):
    """종목이 편입된 ETF 목록 탭."""
    holdings = STOCK_ETFS.get(code, [])
    if not holdings:
        st.caption("ETF 편입 데이터 없음 (주요 지수 미편입 또는 데이터 미등록)")
        return

    st.caption("※ 편입 비율은 운용사 월간 공시 기준 추정치. 실제와 다를 수 있음.")
    st.caption(f"출처: 각 자산운용사 포트폴리오 공시 (분기 갱신)")
    st.divider()

    for h in sorted(holdings, key=lambda x: x.weight_pct, reverse=True):
        perf = fetch_etf_performance(h.etf_code)
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{h.etf_name}**")
                st.caption(f"{h.provider}  |  {h.etf_code}")
            with c2:
                st.metric("편입 비율", f"{h.weight_pct:.1f}%")

            if perf["ok"]:
                col1, col2, col3 = st.columns(3)
                col1.metric("현재가",    f"{perf['price']:,.0f}원")
                col2.metric("1년 수익률", f"{perf['ret_1y']:+.1f}%")
                col3.metric("규모",
                    f"{perf['market_cap']/1e12:.1f}조" if perf["market_cap"] > 1e11
                    else f"{perf['market_cap']/1e8:.0f}억")
            else:
                st.caption("시세 조회 실패")


def render_sector_etfs(sector_name: str):
    """섹터 분석 결과 하단 ETF 추천 블록."""
    etf_list = SECTOR_ETFS.get(sector_name, [])
    if not etf_list:
        return

    with st.expander(f"📦 {sector_name} 관련 ETF 추천", expanded=False):
        st.caption("해당 섹터에 투자하는 주요 ETF 목록 (수익률 순 정렬)")
        st.caption("출처: 각 자산운용사 공시 | 수익률: Yahoo Finance 1년 기준")
        st.divider()

        etf_rows = []
        for etf in etf_list:
            if "확인" in etf.code:   # 코드 미확정 항목 스킵
                continue
            perf = fetch_etf_performance(etf.code)
            etf_rows.append((etf, perf))

        # 1년 수익률 내림차순 정렬
        etf_rows.sort(key=lambda x: x[1]["ret_1y"], reverse=True)

        for etf, perf in etf_rows:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{etf.name}**")
                    st.caption(f"{etf.provider}  |  {etf.code}")
                with c2:
                    if perf["ok"]:
                        color = "buy" if perf["ret_1y"] > 0 else "sell"
                        st.markdown(
                            f'<span class="{color}">{perf["ret_1y"]:+.1f}%</span>',
                            unsafe_allow_html=True,
                        )

                if perf["ok"]:
                    col1, col2 = st.columns(2)
                    col1.metric("현재가", f"{perf['price']:,.0f}원")
                    col2.metric("규모",
                        f"{perf['market_cap']/1e12:.1f}조" if perf["market_cap"] > 1e11
                        else f"{perf['market_cap']/1e8:.0f}억")
                else:
                    st.caption("시세 조회 실패")


# ── 종목 카드 ────────────────────────────────────────────────────────────
CONF_RANK = {"높음": 3, "중간": 2, "낮음": 1}
CONF_STARS = {"높음": "★★★", "중간": "★★☆", "낮음": "★☆☆"}


def _render_card_detail(v, real_data):
    """확장된 종목 상세 (펼쳤을 때 내용)."""
    # 핵심 수치 한 줄
    m = v.metrics
    cols = st.columns(4)
    cols[0].metric("매출성장",  m["매출성장"])
    cols[1].metric("영익률",    m["영업이익률"])
    cols[2].metric("PER",       m["PER"])
    cols[3].metric("1년수익률", m["1년수익률"])

    # 판정 요약
    st.info(v.reasons[-1], icon="💡")

    # 탭: 지표 / 수주분석 / 뉴스 / ETF
    tab_metric, tab_contract, tab_news, tab_etf = st.tabs([
        "📊 지표 상세", "🏗️ 수주·계약", "📰 관련 뉴스", "📦 ETF 편입"
    ])
    with tab_metric:
        _render_metrics_tab(v, real_data)
    with tab_contract:
        biz_model = v.metrics.get("biz_model", "혼합")
        _render_contract_tab(v.code, v.name, biz_model)
    with tab_news:
        _render_news_tab(v.name)
    with tab_etf:
        _render_etf_tab(v.code)


def render_verdict_card(v, real_data, action_css: str, action_label: str):
    """셀(요약 행) + 클릭 시 펼쳐지는 상세."""
    m = v.metrics
    stars = CONF_STARS.get(v.confidence, "")
    # expander 라벨 = 한 줄 요약 셀
    label = (f"{action_label}  {stars} {v.confidence}  |  "
             f"{v.name} ({v.code})  |  "
             f"매출 {m['매출성장']} · 영익 {m['영업이익률']} · "
             f"1년 {m['1년수익률']}")
    with st.expander(label, expanded=False):
        _render_card_detail(v, real_data)


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

        # 종목별 biz_model 추출
        biz_model_map = {
            code: vc.g.nodes[code].get("biz_model", "혼합")
            for code in vc.g.nodes()
        }

        verdicts = []
        for s in scores:
            d = all_data.get(s.code)
            if not d:
                continue
            classified = clf.classify(s, d.market_signals)
            vrd = make_verdict(classified, s, d.market_signals, d)
            vrd.metrics["biz_model"] = biz_model_map.get(s.code, "혼합")
            verdicts.append((vrd, d))

        # 확신 강도순 정렬 (높음 → 중간 → 낮음)
        def _conf_key(item):
            return CONF_RANK.get(item[0].confidence, 0)

        buy_list  = sorted([(v, d) for v, d in verdicts if v.action == "BUY"],
                           key=_conf_key, reverse=True)
        hold_list = sorted([(v, d) for v, d in verdicts if v.action == "HOLD"],
                           key=_conf_key, reverse=True)
        sell_list = sorted([(v, d) for v, d in verdicts if v.action in ("SELL", "AVOID")],
                           key=_conf_key, reverse=True)

        if buy_list:
            st.markdown(f"### ✅ BUY 추천 ({len(buy_list)}종목) — 확신 강한 순")
            st.caption("종목 셀을 누르면 지표·수주·뉴스·ETF 상세가 펼쳐집니다.")
            for v, d in buy_list:
                render_verdict_card(v, d, "▲ BUY", "▲ BUY")

        if hold_list:
            st.markdown(f"### ➖ HOLD ({len(hold_list)}종목) — 확신 강한 순")
            for v, d in hold_list:
                render_verdict_card(v, d, "- HOLD", "- HOLD")

        if sell_list:
            st.markdown(f"### ❌ SELL / AVOID ({len(sell_list)}종목) — 확신 강한 순")
            for v, d in sell_list:
                label = "▼ SELL" if v.action == "SELL" else "× AVOID"
                render_verdict_card(v, d, label, label)

        # 섹터 관련 ETF 추천 블록
        render_sector_etfs(sector_name)


# ── 메인 UI ─────────────────────────────────────────────────────────────
st.title("📈 ValueChain 주식 추천")

now_kst = datetime.now(KST)
market_status = "🟢 장중 (60초 자동 갱신)" if _is_market_hours() else "🔴 장 마감"
st.caption(f"{now_kst.strftime('%Y-%m-%d %H:%M KST')}  {market_status}")
st.caption("※ 투자 자문 아님. 후보 추리기 참고 자료.")

# 증시 지수·환율 상단 자동 표시
render_index_bar()

# 원자재 가격 상단 위젯
render_commodity_widget()

st.divider()
mode = st.radio("분석 방식", ["🔥 뉴스 기반 자동 감지", "📂 섹터 직접 선택"], horizontal=True)

if mode == "🔥 뉴스 기반 자동 감지":
    # 세상 상황 → 수혜 섹터 시나리오 창
    render_scenario_widget()

    st.caption("🔥 핫한 섹터 5개(지금 주목) + 🛡️ 안정 섹터 5개(경기방어)를 나눠서 보여줍니다.")
    group = st.radio("분석할 그룹", ["🔥 핫한 섹터", "🛡️ 안정 섹터", "둘 다"],
                     horizontal=True)
    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        with st.spinner("뉴스 수집 중 (전체 섹터 측정)..."):
            hot, stable = detect_hot_and_stable(hot_n=5, stable_n=5)

        if group in ("🔥 핫한 섹터", "둘 다"):
            st.header("🔥 핫한 섹터 (지금 시장이 주목)")
            if hot:
                run_analysis([(h.sector, h.top_headlines, h.heat) for h in hot])
            else:
                st.info("핫한 섹터를 찾지 못했습니다.")

        if group in ("🛡️ 안정 섹터", "둘 다"):
            st.header("🛡️ 안정 섹터 (경기방어·꾸준한 수요)")
            if stable:
                run_analysis([(s.sector, s.top_headlines, s.heat) for s in stable])
            else:
                st.info("안정 섹터 후보가 없습니다.")
else:
    from news.theme import SECTOR_QUERIES as _SQ
    all_sectors = list(_SQ.keys())
    selected = st.selectbox("섹터 선택", all_sectors)
    if st.button("🔍 분석 시작", type="primary", use_container_width=True):
        run_analysis([(selected, [], 0)])
