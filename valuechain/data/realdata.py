"""
실 데이터 자동 수집.

yfinance에서 Financials(재무)와 MarketSignals(시장신호)를 자동으로 생성한다.
ShovelDetector와 MaturityClassifier에 바로 넣을 수 있는 형태로 변환.

ValueChain 그래프(공급관계)는 자동화가 불가능한 부분이라 여기서 다루지 않는다.
그래프는 별도로 수동으로 구성하고, 이 모듈은 재무/시세 데이터만 담당한다.
"""
from __future__ import annotations
from dataclasses import dataclass
import warnings

from analysis.shovel import Financials
from analysis.maturity import MarketSignals


@dataclass
class CompanyRealData:
    """한 종목의 실 데이터 묶음."""
    code: str
    name: str
    financials: Financials
    market_signals: MarketSignals


class YfinanceDataProvider:
    """
    yfinance에서 Financials + MarketSignals를 자동 생성.

    사용법:
        provider = YfinanceDataProvider()
        data = provider.fetch('005930')               # 단일 종목
        all_data = provider.fetch_many(['005930', '000660'])  # 여러 종목
    """

    def __init__(self, market: str = "KS"):
        import yfinance  # 지연 import
        self._yf = yfinance
        self._market = market

    def _ticker_sym(self, code: str) -> str:
        return f"{code}.{self._market}"

    def fetch(self, code: str) -> CompanyRealData | None:
        """단일 종목 실 데이터 수집. 실패하면 None 반환."""
        try:
            return self._fetch_one(code)
        except Exception as e:
            print(f"  [경고] {code} 데이터 수집 실패: {e}")
            return None

    def _fetch_one(self, code: str) -> CompanyRealData:
        # KS(코스피) 먼저 시도, 종목명이 코드 형태면 KQ(코스닥)로 재시도
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = self._yf.Ticker(self._ticker_sym(code))
        info = t.info
        name = info.get("longName") or info.get("shortName") or ""

        if not name or name.startswith(code):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t_kq = self._yf.Ticker(f"{code}.KQ")
            info_kq = t_kq.info
            name_kq = info_kq.get("longName") or info_kq.get("shortName") or ""
            if name_kq and not name_kq.startswith(code):
                t, info, name = t_kq, info_kq, name_kq

        if not name:
            name = code

        financials = self._build_financials(code, t)
        signals = self._build_market_signals(code, info, t)
        return CompanyRealData(code=code, name=name,
                               financials=financials, market_signals=signals)

    def _build_financials(self, code: str, ticker) -> Financials:
        """
        연간 재무제표에서 YoY 성장률·영익률 계산.
        최근 2개 연도 비교. 데이터 없으면 0으로 처리.
        """
        try:
            fin = ticker.financials   # 행=항목, 열=연도(최신→과거 순)
            if fin.empty or fin.shape[1] < 2:
                return Financials(code, 0, 0, 0, 0)

            rev_now  = _safe_val(fin, "Total Revenue", 0)
            rev_prev = _safe_val(fin, "Total Revenue", 1)
            op_now   = _safe_val(fin, "Operating Income", 0)
            op_prev  = _safe_val(fin, "Operating Income", 1)

            rev_growth = _growth_pct(rev_prev, rev_now)
            op_growth  = _growth_pct(op_prev, op_now)
            op_margin  = (op_now / rev_now * 100) if rev_now and rev_now > 0 else 0.0

            # 수주잔고는 Yahoo에 없음 → 0 (DART 연동 시 채울 자리)
            return Financials(code,
                              round(rev_growth, 1),
                              round(op_margin, 1),
                              round(op_growth, 1),
                              0.0)
        except Exception:
            return Financials(code, 0, 0, 0, 0)

    def _build_market_signals(self, code: str, info: dict, ticker) -> MarketSignals:
        """
        PER/PBR, 1년 수익률, 시가총액으로 MarketSignals 생성.
        """
        per = info.get("trailingPE") or info.get("forwardPE")
        pbr = info.get("priceToBook")
        market_cap = float(info.get("marketCap") or 0)

        # 1년 수익률: 과거 1년 종가 히스토리에서 직접 계산 (가장 정확)
        price_return_1y = 0.0
        try:
            hist = ticker.history(period="1y")
            if len(hist) >= 2:
                price_return_1y = (
                    hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1
                ) * 100
        except Exception:
            pass

        return MarketSignals(
            code=code,
            per=float(per) if per else None,
            pbr=float(pbr) if pbr else None,
            price_return_1y=round(price_return_1y, 1),
            market_cap=market_cap,
        )

    def fetch_many(self, codes: list[str]) -> dict[str, CompanyRealData]:
        """여러 종목. 실패한 종목은 결과에서 제외."""
        result = {}
        for code in codes:
            data = self.fetch(code)
            if data is not None:
                result[code] = data
        return result


# --- 헬퍼 ----------------------------------------------------------------

def _safe_val(df, row_name: str, col_idx: int) -> float:
    """DataFrame에서 안전하게 값 추출."""
    if row_name not in df.index:
        return 0.0
    val = df.loc[row_name].iloc[col_idx]
    if val is None:
        return 0.0
    try:
        v = float(val)
        return 0.0 if (v != v) else v  # NaN 체크
    except (TypeError, ValueError):
        return 0.0


def _growth_pct(prev: float, now: float) -> float:
    """전년 대비 성장률(%). prev가 0이거나 음수면 0 반환."""
    if not prev or prev <= 0:
        return 0.0
    return (now - prev) / prev * 100
