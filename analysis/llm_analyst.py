"""
LLM(Claude) 기반 종목 심층 분석.

규칙 기반 배지(저평가/고평가, 추세)는 verdict.py에서 즉시 계산되고,
이 모듈은 '펼친 종목 1개'에 대해서만 on-demand로 호출되어
자연어 상승/하락 논리를 생성한다.

원칙(프로젝트 핸드오프 문서 준수):
  - API 키는 환경변수/시크릿(ANTHROPIC_API_KEY)으로만. 하드코딩 금지.
  - 환각 방지: 제공된 데이터·뉴스 안에서만 판단하도록 프롬프트로 강제.
  - 구체적 목표가 예측 금지 — '변동 추이/방향'만.
  - 투자 자문 아님(면책).
  - 키가 없으면 None 반환 → 앱은 규칙 기반 배지로 폴백.
"""
from __future__ import annotations
import os
import json
from dataclasses import dataclass


@dataclass
class LLMAnalysis:
    valuation: str       # 저평가 / 적정 / 고평가
    trend: str           # 상승우호 / 중립 / 하락부담
    summary: str         # 2~3문장 핵심 논리
    bull: list[str]      # 상승 논거
    bear: list[str]      # 하락/리스크 논거
    raw: str = ""        # 원문 (디버그용)


def is_available() -> bool:
    """API 키가 설정돼 있는지."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


SYSTEM_PROMPT = (
    "너는 한국 주식 밸류체인 애널리스트다. "
    "제공된 '데이터'와 '뉴스 제목' 안에서만 판단하라. "
    "데이터에 없는 수치·사실을 지어내지 마라(환각 금지). "
    "구체적 목표주가나 '얼마까지 오른다'는 예측은 하지 마라. "
    "오직 '방향(상승우호/중립/하락부담)'과 '밸류(저평가/적정/고평가)'만 판단하라. "
    "이것은 투자 자문이 아니라 후보 선별 참고 자료다. "
    "반드시 아래 JSON 형식으로만 답하라:\n"
    '{"valuation":"저평가|적정|고평가",'
    '"trend":"상승우호|중립|하락부담",'
    '"summary":"2~3문장 핵심 논리",'
    '"bull":["상승 논거1","논거2"],'
    '"bear":["하락/리스크 논거1","논거2"]}'
)


def analyze_stock(verdict, real, news_titles: list[str],
                  model: str = "claude-sonnet-4-6") -> LLMAnalysis | None:
    """
    종목 1개를 Claude로 심층 분석. 키 없거나 실패 시 None.
    """
    if not is_available():
        return None

    try:
        import anthropic
    except ImportError:
        return None

    f = real.financials
    sig = real.market_signals
    m = verdict.metrics

    data_block = (
        f"종목: {verdict.name} ({verdict.code})\n"
        f"매출성장(YoY): {f.revenue_growth_yoy:+.1f}%\n"
        f"영업이익성장(YoY): {f.op_profit_growth_yoy:+.1f}%\n"
        f"영업이익률: {f.op_margin:.1f}%\n"
        f"PER: {sig.per}\n"
        f"PBR: {sig.pbr}\n"
        f"1년 주가수익률: {sig.price_return_1y:+.1f}%\n"
        f"시가총액: {sig.market_cap/1e12:.2f}조원\n"
        f"곡괭이점수(밸류체인 구조강도): {m.get('곡괭이점수')}\n"
        f"성숙도 분류: {m.get('4분면')}\n"
        f"규칙기반 판정: {verdict.action} (확신 {verdict.confidence})\n"
    )
    news_block = "\n".join(f"- {t}" for t in news_titles[:8]) or "(관련 뉴스 없음)"

    user_msg = (
        f"[데이터]\n{data_block}\n[최근 뉴스 제목]\n{news_block}\n\n"
        "위 데이터와 뉴스만 근거로, 이 종목의 밸류(저평가/적정/고평가)와 "
        "방향(상승우호/중립/하락부담)을 판단하고 JSON으로 답하라."
    )

    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=model,
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text.strip()
        # JSON 추출 (코드펜스 등 제거)
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return None
        obj = json.loads(text[start:end + 1])
        return LLMAnalysis(
            valuation=obj.get("valuation", "적정"),
            trend=obj.get("trend", "중립"),
            summary=obj.get("summary", ""),
            bull=obj.get("bull", []),
            bear=obj.get("bear", []),
            raw=text,
        )
    except Exception:
        return None
