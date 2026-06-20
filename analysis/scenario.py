"""
거시 상황(전쟁·금리·환율 등) → 수혜/피해 섹터 매핑.

"세상이 이렇게 바뀌면 어디가 뜨는가"를 규칙 기반으로 정리한다.
AI 예측이 아니라, 과거 인과 패턴을 정리한 참고 시나리오다.

각 시나리오는:
  - 상황 설명
  - 수혜 섹터 / 피해 섹터 (+ 한 줄 근거)
  - 확인할 경제지표 (현재값은 app.py에서 실시간 주입)
  - 관련 뉴스 검색어
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Scenario:
    key: str
    title: str
    summary: str
    winners: list[tuple[str, str]]   # (섹터, 근거)
    losers: list[tuple[str, str]]    # (섹터, 근거)
    watch_indicators: list[str]      # 확인할 지표 이름
    news_query: str                  # 관련 뉴스 검색어


SCENARIOS: list[Scenario] = [
    Scenario(
        key="war_end",
        title="🕊️ 전쟁 종료 / 휴전",
        summary="지정학 리스크가 풀리면 안전자산 수요가 줄고, "
                "전후 재건·물류·교역이 살아난다. 유가·곡물 등 공급망 병목이 해소된다.",
        winners=[
            ("건설", "전후 재건 수요 — 인프라·주택 대규모 발주"),
            ("철강", "재건에 필요한 기초 소재 수요 급증"),
            ("무역", "교역로 정상화 — 원자재·곡물 트레이딩 회복"),
            ("자동차", "공급망 정상화 + 소비심리 회복"),
            ("조선", "교역 회복 → 상선 발주, 유가 안정"),
        ],
        losers=[
            ("방산", "전시 특수 소멸 — 무기 수주 모멘텀 둔화 우려"),
        ],
        watch_indicators=["WTI원유", "금(Gold)", "USD/KRW"],
        news_query="종전 협상 휴전 재건",
    ),
    Scenario(
        key="war_escalate",
        title="⚔️ 지정학 긴장 고조 / 전쟁 확대",
        summary="분쟁이 커지면 안전자산(금)·에너지 가격이 뛰고, "
                "각국이 국방 예산을 늘린다. 공급망 불안으로 원자재가 출렁인다.",
        winners=[
            ("방산", "국방비 증액 — 무기 수출·수주 확대"),
            ("우주항공", "위성·정찰 등 안보 수요 증가"),
            ("조선", "LNG선·함정 수요 (에너지 안보)"),
        ],
        losers=[
            ("자동차", "원자재·물류비 상승, 소비 위축"),
            ("온라인쇼핑", "소비심리 둔화"),
        ],
        watch_indicators=["금(Gold)", "WTI원유", "천연가스"],
        news_query="지정학 리스크 분쟁 국방예산",
    ),
    Scenario(
        key="rate_cut",
        title="📉 금리 인하",
        summary="금리가 내리면 미래 이익의 현재가치가 커져 성장주가 유리하다. "
                "대출 비용이 줄어 건설·부동산·소비가 살아난다.",
        winners=[
            ("바이오", "장기 성장주 — 할인율 하락 수혜 대표"),
            ("온라인게임", "성장주 밸류 재평가"),
            ("건설", "PF·대출 부담 완화, 분양 회복"),
            ("증권/금융", "거래대금↑·IPO·자산가격 상승"),
        ],
        losers=[
            ("증권/금융", "은행 부문은 예대마진 축소 (양면성)"),
        ],
        watch_indicators=["코스피", "나스닥", "USD/KRW"],
        news_query="금리 인하 기준금리 통화정책",
    ),
    Scenario(
        key="rate_hike",
        title="📈 금리 인상 / 고금리 지속",
        summary="금리가 높으면 성장주는 할인율 부담으로 눌리고, "
                "이자 수익이 커지는 은행·보험이 유리하다.",
        winners=[
            ("증권/금융", "예대마진·이자이익 확대 (은행·보험)"),
            ("지주사", "배당·현금흐름 안정 — 방어적 선호"),
        ],
        losers=[
            ("바이오", "할인율 부담 — 성장주 밸류 압박"),
            ("건설", "PF 비용↑·분양 둔화"),
            ("온라인게임", "성장주 멀티플 축소"),
        ],
        watch_indicators=["나스닥", "코스피", "USD/KRW"],
        news_query="금리 인상 고금리 긴축",
    ),
    Scenario(
        key="weak_won",
        title="💵 달러 강세 / 원화 약세",
        summary="환율이 오르면(원화 약세) 해외 매출 비중이 큰 수출주의 "
                "원화 환산 실적이 좋아진다. 반대로 수입·해외여행은 비용 부담.",
        winners=[
            ("반도체", "수출 비중 절대적 — 환차익"),
            ("자동차", "해외 판매 원화 환산 실적 개선"),
            ("조선", "달러 표시 수주 — 원화 환산 증가"),
            ("전자부품", "수출 비중 높음"),
        ],
        losers=[
            ("항공/여행(참고)", "유류·리스비 달러 결제 부담"),
            ("외식/식품", "수입 원재료 비용 상승"),
        ],
        watch_indicators=["USD/KRW", "코스피"],
        news_query="원달러 환율 원화 약세 수출",
    ),
    Scenario(
        key="ai_boom",
        title="🤖 AI 투자 확대 / 데이터센터 붐",
        summary="AI 수요가 커지면 연산용 반도체와 이를 돌릴 전력 인프라가 "
                "함께 필요하다. '곡괭이' 관점에서 부품·소재·전력이 핵심.",
        winners=[
            ("반도체", "HBM·고성능 메모리 수요 폭증"),
            ("AI/전력", "데이터센터 전력 — 변압기·전력기기 수주"),
            ("전기설비", "전력망 증설 — 배전·변압기"),
            ("전자부품", "고다층 기판·MLCC 수요"),
            ("반도체소재", "공정 미세화 — 소재 사용량 증가"),
        ],
        losers=[],
        watch_indicators=["나스닥", "코스피"],
        news_query="AI 데이터센터 전력 반도체 투자",
    ),
    Scenario(
        key="oil_spike",
        title="🛢️ 유가 급등",
        summary="유가가 오르면 정유·에너지·자원개발이 수혜를 보고, "
                "연료비 비중이 큰 항공·화학·운송은 비용 압박을 받는다.",
        winners=[
            ("조선", "고유가 → 해양플랜트·LNG선 발주 환경"),
            ("무역", "자원·에너지 트레이딩 마진 확대"),
        ],
        losers=[
            ("자동차", "원가·물류비 상승, 소비 둔화"),
            ("외식/식품", "물류·포장재 비용 상승"),
        ],
        watch_indicators=["WTI원유", "천연가스", "USD/KRW"],
        news_query="국제유가 급등 원유 OPEC",
    ),
    Scenario(
        key="china_stimulus",
        title="🐉 중국 경기 부양",
        summary="중국이 경기를 부양하면 원자재·소재 수요가 살아난다. "
                "한국의 소재·화학·화장품·여행 관련주가 영향을 받는다.",
        winners=[
            ("철강", "중국 건설·인프라 수요 — 가격 반등"),
            ("생활소비재", "중국 소비 회복 — K뷰티 수출"),
            ("유통", "중국인 관광·면세 회복"),
        ],
        losers=[],
        watch_indicators=["구리(Copper)", "철광석(ETF)"],
        news_query="중국 경기부양 부동산 소비",
    ),
]


def get_scenario(key: str) -> Scenario | None:
    for s in SCENARIOS:
        if s.key == key:
            return s
    return None
