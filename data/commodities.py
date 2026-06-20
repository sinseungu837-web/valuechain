"""
원자재·광물 실시간 가격 조회 (yfinance).

금·은·구리·원유·천연가스·USD/KRW 등
"""
from __future__ import annotations
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

COMMODITY_MAP = {
    "금(Gold)":       ("GC=F",  "USD/oz",  1),
    "은(Silver)":     ("SI=F",  "USD/oz",  1),
    "구리(Copper)":   ("HG=F",  "USD/lb",  1),
    "WTI원유":        ("CL=F",  "USD/bbl", 1),
    "천연가스":       ("NG=F",  "USD/MMBtu",1),
    "USD/KRW":        ("KRW=X", "KRW",     1),
    "철광석(ETF)":    ("PICK",  "USD",     1),   # VanEck Mining ETF (근사치)
}

# 단위·가격기준 설명 (설명 버튼용). 핵심만 짧게.
COMMODITY_INFO = {
    "금(Gold)": (
        "**단위: USD/온스(oz)** — 1트로이온스 ≈ 31.1g 기준 달러 가격.\n\n"
        "안전자산의 대표. 금리·달러가 내리거나 불확실성↑일 때 오르는 경향. "
        "인플레이션 헤지 수단으로도 쓰임."
    ),
    "은(Silver)": (
        "**단위: USD/온스(oz)** — 금과 같은 트로이온스 기준.\n\n"
        "금처럼 안전자산이면서 산업금속(태양광·전자) 성격도 강해 "
        "변동성이 금보다 큼. 금/은 비율(Gold-Silver Ratio)로 상대 저평가를 봄."
    ),
    "구리(Copper)": (
        "**단위: USD/파운드(lb)** — 1파운드 ≈ 453.6g 기준.\n\n"
        "'닥터 코퍼'. 전선·건설·전기차에 필수라 경기·제조업 경기의 선행지표로 통함. "
        "오르면 경기 확장 신호로 해석."
    ),
    "WTI원유": (
        "**단위: USD/배럴(bbl)** — 1배럴 ≈ 159리터 기준.\n\n"
        "WTI는 미국산 경질유 기준가(서부텍사스산원유). "
        "유가↑는 정유·조선·에너지엔 호재, 항공·화학·운송엔 비용 부담."
    ),
    "천연가스": (
        "**단위: USD/MMBtu** — 100만 영국열량단위(British Thermal Unit) 기준.\n\n"
        "난방·발전 연료. 계절(겨울)·지정학(전쟁·LNG 수급)에 민감. "
        "LNG선·가스터빈 관련주와 연동."
    ),
    "USD/KRW": (
        "**단위: 원(KRW)** — 1달러를 사는 데 필요한 원화.\n\n"
        "환율↑(원화 약세)는 수출주(반도체·자동차·조선)에 유리, "
        "원자재 수입·항공엔 불리. 외국인 자금 흐름과도 연결."
    ),
    "철광석(ETF)": (
        "**참고: VanEck 광산 ETF(PICK) 가격, USD.**\n\n"
        "철광석 선물 직접 시세가 아니라 글로벌 광산기업 묶음 가격으로 "
        "추세를 근사. 철강·조선·건설 수요와 연동."
    ),
}


# 주요 증시 지수 + 환율 (상단 자동 표시용)
INDEX_MAP = {
    "코스피":    ("^KS11",  "pt"),
    "코스닥":    ("^KQ11",  "pt"),
    "나스닥":    ("^IXIC",  "pt"),
    "S&P500":    ("^GSPC",  "pt"),
    "원/달러":   ("KRW=X",  "원"),
    "원/엔(100)":("JPYKRW=X","원"),
}


@dataclass
class CommodityPrice:
    name: str
    symbol: str
    unit: str
    price: float
    chg_pct: float    # 전일 대비 %
    fetched_at: str
    price_krw: float = 0.0   # 원화 환산 (USD 표시 항목만, 같은 단위 기준)


def _get_usdkrw() -> float:
    """현재 USD/KRW 환율 (원화 환산용)."""
    import yfinance as yf
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            info = yf.Ticker("KRW=X").info
        return (info.get("regularMarketPrice")
                or info.get("previousClose") or 0)
    except Exception:
        return 0.0


def fetch_index_prices() -> list[CommodityPrice]:
    """코스피·코스닥·나스닥·S&P500 지수 + 환율 조회."""
    import yfinance as yf
    results = []
    for name, (symbol, unit) in INDEX_MAP.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = yf.Ticker(symbol)
            info = t.info
            price = (info.get("regularMarketPrice")
                     or info.get("currentPrice")
                     or info.get("previousClose", 0))
            prev  = info.get("previousClose") or price
            # 원/엔은 100엔 기준으로 환산
            if name == "원/엔(100)" and price:
                price *= 100
                prev  *= 100
            chg_p = (price - prev) / prev * 100 if prev else 0
            results.append(CommodityPrice(
                name=name, symbol=symbol, unit=unit,
                price=price, chg_pct=round(chg_p, 2),
                fetched_at=datetime.now(KST).strftime("%H:%M KST"),
            ))
        except Exception:
            results.append(CommodityPrice(name, symbol, unit, 0, 0, "-"))
    return results


def fetch_commodity_prices() -> list[CommodityPrice]:
    """주요 원자재 현재가·등락률 조회 (60초 미만 캐시는 app.py에서 처리)."""
    import yfinance as yf
    results = []
    usdkrw = _get_usdkrw()   # 원화 환산용 환율

    for name, (symbol, unit, _) in COMMODITY_MAP.items():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = yf.Ticker(symbol)
            info = t.info
            price = (info.get("regularMarketPrice")
                     or info.get("currentPrice")
                     or info.get("previousClose", 0))
            prev  = info.get("previousClose") or price
            chg_p = (price - prev) / prev * 100 if prev else 0

            # USD 표시 항목은 원화로 환산 (같은 단위 기준: USD/oz → 원/oz)
            krw = 0.0
            if name == "USD/KRW":
                krw = 0.0  # 이미 환율 자체
            elif usdkrw and price:
                krw = price * usdkrw

            results.append(CommodityPrice(
                name=name,
                symbol=symbol,
                unit=unit,
                price=price,
                chg_pct=round(chg_p, 2),
                fetched_at=datetime.now(KST).strftime("%H:%M KST"),
                price_krw=round(krw, 0),
            ))
        except Exception:
            results.append(CommodityPrice(name, symbol, unit, 0, 0, "-", 0.0))

    return results
