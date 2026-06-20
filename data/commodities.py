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


@dataclass
class CommodityPrice:
    name: str
    symbol: str
    unit: str
    price: float
    chg_pct: float    # 전일 대비 %
    fetched_at: str


def fetch_commodity_prices() -> list[CommodityPrice]:
    """주요 원자재 현재가·등락률 조회 (60초 미만 캐시는 app.py에서 처리)."""
    import yfinance as yf
    results = []

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

            results.append(CommodityPrice(
                name=name,
                symbol=symbol,
                unit=unit,
                price=price,
                chg_pct=round(chg_p, 2),
                fetched_at=datetime.now(KST).strftime("%H:%M KST"),
            ))
        except Exception:
            results.append(CommodityPrice(name, symbol, unit, 0, 0, "-"))

    return results
