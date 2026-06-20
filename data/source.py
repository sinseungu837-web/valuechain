"""
데이터 소스 추상화 계층.

핵심 아이디어:
    프로그램의 나머지 부분은 '어디서' 데이터가 오는지 전혀 모른다.
    오직 MarketDataSource 인터페이스만 안다.
    -> 지금은 SampleSource로 개발하고,
       나중에 PykrxSource / TossSource 구현체만 끼워넣으면 끝.

이게 'API 키를 기다리는 동안 80%를 미리 만든다'의 실체다.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class Quote:
    """한 종목의 시세 스냅샷 (소스가 무엇이든 이 형태로 통일)."""
    code: str           # 종목코드 '005930'
    name: str           # 종목명 '삼성전자'
    price: float        # 현재가(또는 종가)
    market_cap: float   # 시가총액 (원)
    change_pct: float   # 등락률 (%)
    volume: int         # 거래량
    per: float | None = None
    pbr: float | None = None


class MarketDataSource(ABC):
    """모든 데이터 소스가 지켜야 하는 계약(interface)."""

    @abstractmethod
    def get_quote(self, code: str) -> Quote:
        """단일 종목 시세."""
        ...

    @abstractmethod
    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        """여러 종목 시세 (기본 구현은 get_quote 반복)."""
        ...

    def name(self) -> str:
        return self.__class__.__name__


class SampleSource(MarketDataSource):
    """
    외부 연결 없이 도는 더미 소스.
    개발·테스트·데모용. 실제 값과 무관한 고정 샘플.
    """
    _DB = {
        "005930": ("삼성전자",        71000,  423_000_000_000_000,  1.2, 12_000_000, 14.1, 1.3),
        "000660": ("SK하이닉스",      178000, 129_000_000_000_000,  2.8,  4_500_000, 9.8,  1.9),
        "042700": ("한미반도체",      98000,   9_500_000_000_000, -1.5,  1_200_000, 35.0, 8.1),
        "058470": ("리노공업",        148000,  2_300_000_000_000,  0.4,    180_000, 22.0, 4.5),
        "240810": ("원익IPS",         32000,   1_600_000_000_000, -0.9,    900_000, 18.0, 1.7),
        "403870": ("HPSP",           38000,   3_100_000_000_000,  3.1,    700_000, 28.0, 9.0),
        "095340": ("ISC",            68000,   1_300_000_000_000,  1.8,    250_000, 24.0, 3.2),
    }

    def get_quote(self, code: str) -> Quote:
        if code not in self._DB:
            raise KeyError(f"샘플DB에 없는 종목: {code}")
        n, p, mc, ch, vol, per, pbr = self._DB[code]
        return Quote(code, n, p, mc, ch, vol, per, pbr)

    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        return {c: self.get_quote(c) for c in codes if c in self._DB}


# --- 나중에 추가할 구현체 (지금은 스텁) ----------------------------------
class PykrxSource(MarketDataSource):
    """
    실제 한국거래소 데이터 (pykrx 기반).
    - OHLCV: 안정적으로 동작
    - 시가총액/PER/PBR: KRX 서버 상태에 따라 실패 가능 → None 반환
    """
    def __init__(self):
        from pykrx import stock  # 지연 import (인터넷 없는 환경 대비)
        self._stock = stock

    def _latest_trading_date(self) -> str:
        """오늘부터 거슬러 올라가며 OHLCV 데이터가 있는 가장 최근 거래일 반환."""
        from datetime import date, timedelta
        for delta in range(7):
            d = (date.today() - timedelta(days=delta)).strftime("%Y%m%d")
            try:
                df = self._stock.get_market_ohlcv_by_date(d, d, "005930")
                if not df.empty:
                    return d
            except Exception:
                continue
        raise RuntimeError("최근 7일 이내 거래일 데이터를 찾을 수 없음")

    def get_quote(self, code: str) -> Quote:
        trading_date = self._latest_trading_date()

        # OHLCV (현재가·거래량·등락률) — 안정적
        ohlcv = self._stock.get_market_ohlcv_by_date(trading_date, trading_date, code)
        if ohlcv.empty:
            raise KeyError(f"pykrx: 종목코드 {code}의 OHLCV 데이터 없음 (날짜: {trading_date})")
        row = ohlcv.iloc[-1]
        price = float(row.iloc[3])       # 종가
        volume = int(row.iloc[4])        # 거래량
        change_pct = float(row.iloc[5])  # 등락률

        # 종목명 조회 (실패하거나 str이 아니면 코드로 대체)
        try:
            name = self._stock.get_market_ticker_name(code)
            if not isinstance(name, str) or not name:
                name = code
        except Exception:
            name = code

        # 시가총액 — 실패 시 None
        market_cap: float | None = None
        try:
            cap_df = self._stock.get_market_cap_by_date(trading_date, trading_date, code)
            if not cap_df.empty:
                market_cap = float(cap_df.iloc[-1, 0])
        except Exception:
            pass

        # PER/PBR — 실패 시 None
        per: float | None = None
        pbr: float | None = None
        try:
            fund_df = self._stock.get_market_fundamental_by_date(trading_date, trading_date, code)
            if not fund_df.empty:
                per = float(fund_df.iloc[-1]["PER"])
                pbr = float(fund_df.iloc[-1]["PBR"])
        except Exception:
            pass

        return Quote(code, name, price, market_cap or 0.0, change_pct, volume, per, pbr)

    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        results = {}
        for code in codes:
            try:
                results[code] = self.get_quote(code)
            except Exception as e:
                print(f"  [경고] {code} 조회 실패: {e}")
        return results


class YfinanceSource(MarketDataSource):
    """
    Yahoo Finance 기반 실 데이터 소스.
    KRX/pykrx 서버 의존 없이 안정적으로 동작.
    코스피: code.KS / 코스닥: code.KQ
    """
    def __init__(self, market: str = "KS"):
        import yfinance  # 지연 import
        self._yf = yfinance
        self._market = market  # "KS"(코스피) or "KQ"(코스닥)

    def _ticker(self, code: str) -> str:
        return f"{code}.{self._market}"

    def get_quote(self, code: str) -> Quote:
        t = self._yf.Ticker(self._ticker(code))
        info = t.info

        price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
        if price == 0:
            raise KeyError(f"yfinance: {code} 가격 데이터 없음")

        market_cap = float(info.get("marketCap") or 0)
        volume = int(info.get("volume") or info.get("regularMarketVolume") or 0)
        prev_close = float(info.get("previousClose") or info.get("regularMarketPreviousClose") or price)
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0.0
        name = info.get("longName") or info.get("shortName") or code
        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")

        return Quote(code, name, price, market_cap, round(change_pct, 2), volume,
                     float(per) if per else None,
                     float(pbr) if pbr else None)

    def get_quotes(self, codes: list[str]) -> dict[str, Quote]:
        results = {}
        for code in codes:
            try:
                results[code] = self.get_quote(code)
            except Exception as e:
                print(f"  [경고] {code} 조회 실패: {e}")
        return results
