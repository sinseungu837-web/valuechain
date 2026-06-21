"""
실제 증권 시장 업종(섹터) 목록 + 업종별 구성 종목.

FinanceDataReader의 'KRX-DESC' 목록을 사용한다.
이 목록은 거래소 공식 업종 분류(한국표준산업분류 기반, Industry)와
종목코드를 함께 담고 있어, '업종 선택 → 구성 종목 자동 후보'가 가능하다.

네트워크/서버 문제로 실패하면 폴백 업종 목록을 반환한다.
시세·재무는 여기서 다루지 않는다(yfinance 자동, STEP 3).
"""
from __future__ import annotations

# FDR 실패 시 폴백 (대표 업종 일부)
_FALLBACK_INDUSTRIES = [
    "반도체 제조업", "전자부품 제조업", "통신 및 방송 장비 제조업",
    "자동차용 엔진 및 자동차 제조업", "1차 철강 제조업", "기초 화학물질 제조업",
    "의약품 제조업", "기초 의약물질 제조업", "건물 건설업", "선박 및 보트 건조업",
    "항공기,우주선 및 부품 제조업", "전동기, 발전기 및 전기 변환장치 제조업",
    "소프트웨어 개발 및 공급업", "기타 금융업", "전기업",
]


def _load_krx_desc():
    """
    KRX-DESC(업종 분류) + KRX(시가총액)를 합친 DataFrame 로드. 실패 시 None.
    KRX-DESC에는 시총이 없어, KRX 목록의 Marcap을 코드로 합쳐 정렬에 쓴다.
    """
    try:
        import FinanceDataReader as fdr
        df = fdr.StockListing("KRX-DESC")
        if df is None or df.empty or "Industry" not in df.columns:
            return None
        # 시가총액 병합 (정렬용)
        try:
            cap = fdr.StockListing("KRX")
            if cap is not None and "Marcap" in cap.columns:
                cap = cap[["Code", "Marcap"]].copy()
                df = df.merge(cap, on="Code", how="left")
        except Exception:
            pass
        return df
    except Exception:
        return None


def get_industries() -> list[str]:
    """거래소 업종(Industry) 목록. 가나다순. 실패 시 폴백."""
    df = _load_krx_desc()
    if df is None:
        return sorted(_FALLBACK_INDUSTRIES)
    inds = sorted(df["Industry"].dropna().unique())
    return [i for i in inds if i]


def stocks_in_industry(industry: str) -> list[dict]:
    """
    해당 업종에 속한 종목 목록.
    반환: [{"code","name","market"}], 시총(있으면) 큰 순.
    실패하면 빈 리스트.
    """
    df = _load_krx_desc()
    if df is None:
        return []
    sub = df[df["Industry"] == industry].copy()
    if sub.empty:
        return []

    # 시총 컬럼이 있으면 큰 순 정렬 (대표 종목 먼저)
    for cap_col in ("Marcap", "MarketCap"):
        if cap_col in sub.columns:
            sub = sub.sort_values(cap_col, ascending=False)
            break

    out = []
    for _, r in sub.iterrows():
        out.append({
            "code": str(r["Code"]),
            "name": str(r.get("Name", "")),
            "market": str(r.get("Market", "")),
        })
    return out
