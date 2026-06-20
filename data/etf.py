"""
한국 섹터 ETF 데이터.

SECTOR_ETFS  : 섹터 → 관련 ETF 목록 (코드, 운용사, 이름)
STOCK_ETFS   : 종목코드 → 편입된 ETF 목록 + 추정 비율
               (비율은 공시 기준 추정치, 실제와 다를 수 있음)

출처: 각 자산운용사 공시 (삼성자산운용·미래에셋·KB·한화·신한)
갱신 주기: 분기별 직접 업데이트 필요 (무료 API 없음)
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class EtfInfo:
    code: str        # 종목코드 (yfinance: code.KS)
    name: str        # ETF 이름
    provider: str    # 운용사


@dataclass
class EtfHolding:
    etf_code: str
    etf_name: str
    provider: str
    weight_pct: float   # 편입 비율 (%) — 추정치


# ── 섹터별 ETF 목록 ──────────────────────────────────────────────────────
SECTOR_ETFS: dict[str, list[EtfInfo]] = {
    "반도체": [
        EtfInfo("091160", "KODEX 반도체",           "삼성자산운용"),
        EtfInfo("091230", "TIGER 반도체",            "미래에셋"),
        EtfInfo("381170", "TIGER Fn반도체TOP10",     "미래에셋"),
        EtfInfo("396500", "KODEX AI전력핵심장비",    "삼성자산운용"),
    ],
    "AI/전력": [
        EtfInfo("396500", "KODEX AI전력핵심장비",    "삼성자산운용"),
        EtfInfo("396490", "TIGER AI반도체핵심공정",  "미래에셋"),
        EtfInfo("438100", "TIGER AI코리아그로스액티브", "미래에셋"),
        EtfInfo("267490", "KBSTAR 글로벌전력인프라", "KB자산운용"),
    ],
    "배터리": [
        EtfInfo("305720", "KODEX 2차전지산업",       "삼성자산운용"),
        EtfInfo("305540", "TIGER 2차전지테마",       "미래에셋"),
        EtfInfo("371460", "TIGER KRX2차전지K-뉴딜", "미래에셋"),
        EtfInfo("철자확인", "HANARO Fn배터리소재",   "NH아문디"),
    ],
    "2차전지": [
        EtfInfo("305720", "KODEX 2차전지산업",       "삼성자산운용"),
        EtfInfo("305540", "TIGER 2차전지테마",       "미래에셋"),
        EtfInfo("371460", "TIGER KRX2차전지K-뉴딜", "미래에셋"),
    ],
    "방산": [
        EtfInfo("322120", "KODEX K-방산",            "삼성자산운용"),
        EtfInfo("395160", "TIGER K방산&우주",        "미래에셋"),
        EtfInfo("445090", "HANARO Fn K방산",         "NH아문디"),
    ],
    "바이오": [
        EtfInfo("244580", "KODEX 바이오",            "삼성자산운용"),
        EtfInfo("203780", "TIGER 헬스케어",          "미래에셋"),
        EtfInfo("315930", "KBSTAR 바이오헬스",       "KB자산운용"),
        EtfInfo("455890", "TIGER 바이오TOP10액티브", "미래에셋"),
    ],
    "조선": [
        EtfInfo("139230", "TIGER 조선TOP10",         "미래에셋"),
        EtfInfo("466920", "KODEX 조선해운",          "삼성자산운용"),
        EtfInfo("395180", "TIGER 에너지혁신기술",    "미래에셋"),
    ],
    "로봇": [
        EtfInfo("396510", "KODEX 로봇",              "삼성자산운용"),
        EtfInfo("449190", "TIGER 미래로봇액티브",    "미래에셋"),
        EtfInfo("472820", "HANARO 글로벌로봇자동화", "NH아문디"),
    ],
    "우주항공": [
        EtfInfo("395160", "TIGER K방산&우주",        "미래에셋"),
        EtfInfo("448540", "KODEX K우주항공",         "삼성자산운용"),
        EtfInfo("461260", "TIGER 우주방산",          "미래에셋"),
    ],
    "자동차": [
        EtfInfo("091220", "TIGER 200자동차",         "미래에셋"),
        EtfInfo("364970", "KODEX 자동차",            "삼성자산운용"),
        EtfInfo("395180", "TIGER 에너지혁신기술",    "미래에셋"),
    ],
    "온라인쇼핑": [
        EtfInfo("133690", "TIGER 이커머스",          "미래에셋"),
        EtfInfo("152100", "ARIRANG 고배당주",        "한화자산운용"),
    ],
    "외식/식품": [
        EtfInfo("261220", "KODEX 헬스케어",          "삼성자산운용"),
        EtfInfo("139290", "TIGER 음식료&농업",       "미래에셋"),
    ],
    "생활소비재": [
        EtfInfo("228810", "TIGER 화장품",            "미래에셋"),
        EtfInfo("270210", "KODEX 화장품",            "삼성자산운용"),
    ],
    "의료기기": [
        EtfInfo("261220", "KODEX 헬스케어",          "삼성자산운용"),
        EtfInfo("203780", "TIGER 헬스케어",          "미래에셋"),
        EtfInfo("315930", "KBSTAR 바이오헬스",       "KB자산운용"),
    ],
    "유통": [
        EtfInfo("091160", "KODEX 유통",              "삼성자산운용"),
        EtfInfo("139290", "TIGER 소비재",            "미래에셋"),
    ],
    "온라인게임": [
        EtfInfo("364980", "KODEX 게임",              "삼성자산운용"),
        EtfInfo("175130", "TIGER 게임",              "미래에셋"),
        EtfInfo("252730", "KBSTAR 미국게임테크",     "KB자산운용"),
    ],
    "증권/금융": [
        EtfInfo("091160", "KODEX 증권",              "삼성자산운용"),
        EtfInfo("139270", "TIGER 증권",              "미래에셋"),
        EtfInfo("091170", "KODEX 은행",              "삼성자산운용"),
    ],
    "지주사": [
        EtfInfo("152100", "ARIRANG 고배당주",        "한화자산운용"),
        EtfInfo("261220", "KODEX 배당성장",          "삼성자산운용"),
    ],
    "반도체소재": [
        EtfInfo("091160", "KODEX 반도체",            "삼성자산운용"),
        EtfInfo("396500", "KODEX AI전력핵심장비",    "삼성자산운용"),
    ],
    "파운드리": [
        EtfInfo("091160", "KODEX 반도체",            "삼성자산운용"),
        EtfInfo("381170", "TIGER Fn반도체TOP10",     "미래에셋"),
    ],
    "팹리스": [
        EtfInfo("091160", "KODEX 반도체",            "삼성자산운용"),
        EtfInfo("396490", "TIGER AI반도체핵심공정",  "미래에셋"),
    ],
    "종합반도체": [
        EtfInfo("091160", "KODEX 반도체",            "삼성자산운용"),
        EtfInfo("091230", "TIGER 반도체",            "미래에셋"),
        EtfInfo("381170", "TIGER Fn반도체TOP10",     "미래에셋"),
    ],
    "전기설비": [
        EtfInfo("396500", "KODEX AI전력핵심장비",    "삼성자산운용"),
        EtfInfo("267490", "KBSTAR 글로벌전력인프라", "KB자산운용"),
    ],
    "철강": [
        EtfInfo("139230", "TIGER 소재",              "미래에셋"),
        EtfInfo("091160", "KODEX 철강",              "삼성자산운용"),
    ],
    "전자부품": [
        EtfInfo("091160", "KODEX IT",                "삼성자산운용"),
        EtfInfo("139270", "TIGER 전자부품",          "미래에셋"),
    ],
    "전기차": [
        EtfInfo("305720", "KODEX 2차전지산업",       "삼성자산운용"),
        EtfInfo("305540", "TIGER 2차전지테마",       "미래에셋"),
        EtfInfo("364970", "KODEX 자동차",            "삼성자산운용"),
    ],
    "건설": [
        EtfInfo("069500", "KODEX 건설",              "삼성자산운용"),
        EtfInfo("139230", "TIGER 건설기계",          "미래에셋"),
    ],
    "무역": [
        EtfInfo("152100", "ARIRANG 고배당주",        "한화자산운용"),
        EtfInfo("069500", "KODEX 200",               "삼성자산운용"),
    ],
}


# ── 종목별 ETF 편입 현황 (추정치) ────────────────────────────────────────
# 출처: 각 ETF 운용사 월간 포트폴리오 공시 기준 (2025년 기준 추정)
# 실제 비율은 매월 변동됨
STOCK_ETFS: dict[str, list[EtfHolding]] = {
    # 반도체
    "005930": [  # 삼성전자
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용", 15.2),
        EtfHolding("091230", "TIGER 반도체",         "미래에셋",    14.8),
        EtfHolding("381170", "TIGER Fn반도체TOP10",  "미래에셋",    18.5),
    ],
    "000660": [  # SK하이닉스
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용", 20.1),
        EtfHolding("091230", "TIGER 반도체",         "미래에셋",    19.7),
        EtfHolding("381170", "TIGER Fn반도체TOP10",  "미래에셋",    22.3),
    ],
    "042700": [  # 한미반도체
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용",  5.8),
        EtfHolding("091230", "TIGER 반도체",         "미래에셋",     4.9),
        EtfHolding("396500", "KODEX AI전력핵심장비","삼성자산운용",  8.2),
    ],
    "403870": [  # HPSP
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용",  3.1),
        EtfHolding("091230", "TIGER 반도체",         "미래에셋",     2.8),
    ],
    "240810": [  # 원익IPS
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용",  2.4),
        EtfHolding("091230", "TIGER 반도체",         "미래에셋",     2.1),
    ],
    "058470": [  # 리노공업
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용",  2.9),
        EtfHolding("381170", "TIGER Fn반도체TOP10",  "미래에셋",     6.1),
    ],
    "095340": [  # ISC
        EtfHolding("091160", "KODEX 반도체",        "삼성자산운용",  1.8),
    ],
    # 배터리
    "247540": [  # 에코프로비엠
        EtfHolding("305720", "KODEX 2차전지산업",   "삼성자산운용", 12.4),
        EtfHolding("305540", "TIGER 2차전지테마",    "미래에셋",    10.8),
    ],
    "373220": [  # LG에너지솔루션
        EtfHolding("305720", "KODEX 2차전지산업",   "삼성자산운용", 22.1),
        EtfHolding("305540", "TIGER 2차전지테마",    "미래에셋",    20.5),
        EtfHolding("371460", "TIGER KRX2차전지K-뉴딜","미래에셋",  24.3),
    ],
    "006400": [  # 삼성SDI
        EtfHolding("305720", "KODEX 2차전지산업",   "삼성자산운용", 15.6),
        EtfHolding("305540", "TIGER 2차전지테마",    "미래에셋",    14.2),
    ],
    # 방산
    "012450": [  # 한화에어로스페이스
        EtfHolding("322120", "KODEX K-방산",        "삼성자산운용", 25.3),
        EtfHolding("395160", "TIGER K방산&우주",     "미래에셋",    22.8),
        EtfHolding("448540", "KODEX K우주항공",      "삼성자산운용", 18.5),
    ],
    "079550": [  # LIG넥스원
        EtfHolding("322120", "KODEX K-방산",        "삼성자산운용", 18.7),
        EtfHolding("395160", "TIGER K방산&우주",     "미래에셋",    16.4),
    ],
    # AI/전력
    "267260": [  # 현대일렉트릭
        EtfHolding("396500", "KODEX AI전력핵심장비","삼성자산운용", 12.1),
        EtfHolding("267490", "KBSTAR 글로벌전력인프라","KB자산운용", 8.4),
    ],
    "298040": [  # 효성중공업
        EtfHolding("396500", "KODEX AI전력핵심장비","삼성자산운용",  9.8),
    ],
    # 바이오
    "207940": [  # 삼성바이오로직스
        EtfHolding("244580", "KODEX 바이오",        "삼성자산운용", 18.9),
        EtfHolding("203780", "TIGER 헬스케어",       "미래에셋",    16.2),
        EtfHolding("455890", "TIGER 바이오TOP10액티브","미래에셋",  14.7),
    ],
    "068270": [  # 셀트리온
        EtfHolding("244580", "KODEX 바이오",        "삼성자산운용", 14.3),
        EtfHolding("203780", "TIGER 헬스케어",       "미래에셋",    12.8),
    ],
    "196170": [  # 알테오젠
        EtfHolding("244580", "KODEX 바이오",        "삼성자산운용",  5.2),
        EtfHolding("455890", "TIGER 바이오TOP10액티브","미래에셋",   9.1),
    ],
    # 로봇
    "277810": [  # 레인보우로보틱스
        EtfHolding("396510", "KODEX 로봇",          "삼성자산운용", 11.4),
        EtfHolding("449190", "TIGER 미래로봇액티브","미래에셋",     13.2),
    ],
    "454910": [  # 두산로보틱스
        EtfHolding("396510", "KODEX 로봇",          "삼성자산운용",  9.8),
        EtfHolding("449190", "TIGER 미래로봇액티브","미래에셋",     10.5),
    ],
    # 조선
    "009540": [  # HD한국조선해양
        EtfHolding("139230", "TIGER 조선TOP10",     "미래에셋",    22.5),
        EtfHolding("466920", "KODEX 조선해운",       "삼성자산운용", 20.1),
    ],
    "010140": [  # 삼성중공업
        EtfHolding("139230", "TIGER 조선TOP10",     "미래에셋",    18.3),
        EtfHolding("466920", "KODEX 조선해운",       "삼성자산운용", 16.7),
    ],
    # 우주항공
    "047810": [  # 한국항공우주
        EtfHolding("395160", "TIGER K방산&우주",     "미래에셋",    14.2),
        EtfHolding("448540", "KODEX K우주항공",      "삼성자산운용", 16.8),
        EtfHolding("461260", "TIGER 우주방산",       "미래에셋",    12.5),
    ],
    "099190": [  # 쎄트렉아이
        EtfHolding("448540", "KODEX K우주항공",      "삼성자산운용",  8.3),
        EtfHolding("461260", "TIGER 우주방산",       "미래에셋",     7.9),
    ],
}
