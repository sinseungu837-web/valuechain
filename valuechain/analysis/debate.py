"""
멀티 AI 토론 분석 엔진.

설계 철학(전에 합의한 내용):
    - 여러 AI를 그냥 평균내면 '같이 틀린다'. 그래서 역할을 나눈다.
    - Bull(상향 논거) vs Bear(하향 논거) vs Judge(종합/판정)
    - 모든 의견은 반드시 '근거'를 달아야 한다. 근거 없는 의견은 버린다.
    - 근거는 밸류체인 그래프 + 시세 스냅샷에서만 나와야 한다(환각 방지).

이 파일은 '구조'다. 실제 LLM 호출부는 LLMClient를 상속해
네 환경에서 Claude/Gemini API 키로 채우면 된다.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class Role(Enum):
    BULL = "상향론자"
    BEAR = "하향론자"
    JUDGE = "심판"


@dataclass
class Evidence:
    """근거 하나. 반드시 실제 데이터에 연결되어야 한다."""
    kind: str      # 'valuechain' | 'marketcap' | 'tech' | 'price'
    detail: str    # 사람이 읽는 설명
    refs: list[str] = field(default_factory=list)  # 참조한 종목코드/기술태그


@dataclass
class Opinion:
    role: Role
    model: str             # 'claude' | 'gemini' ...
    stance: str            # '상향' | '하향' | '중립'
    confidence: float      # 0~1
    thesis: str            # 한 줄 핵심 주장
    evidence: list[Evidence]

    def is_valid(self) -> bool:
        """근거 없는 의견은 무효 처리."""
        return len(self.evidence) > 0 and bool(self.thesis.strip())


@dataclass
class Verdict:
    """심판의 최종 종합."""
    final_stance: str
    confidence: float
    rationale: str
    bull_points: list[str]
    bear_points: list[str]


class LLMClient(ABC):
    """
    실제 AI 모델 래퍼. 네 환경에서 구현:
        class ClaudeClient(LLMClient): ...  (anthropic SDK)
        class GeminiClient(LLMClient): ...  (google-genai SDK)
    """
    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        ...


def build_prompt(role: Role, context: str) -> tuple[str, str]:
    """
    역할별 시스템/유저 프롬프트 생성.
    근거 강제 + 그래프 데이터 한정이 핵심.
    """
    common = (
        "너는 한국 주식 산업분석가다. 반드시 아래 제공된 밸류체인/시세 "
        "데이터에 근거해서만 의견을 낸다. 데이터에 없는 사실을 지어내지 마라. "
        "각 주장마다 어떤 종목코드나 기술에 근거했는지 명시하라."
    )
    if role is Role.BULL:
        sys = common + " 너는 이 산업/종목의 '상승 논거'를 최대한 강하게 찾는다."
    elif role is Role.BEAR:
        sys = common + " 너는 이 산업/종목의 '하락 위험'을 최대한 날카롭게 찾는다."
    else:
        sys = (common + " 너는 심판이다. 상향론자와 하향론자의 주장을 비교해 "
               "어느 쪽 근거가 데이터로 더 탄탄한지 판정하고 최종 의견을 낸다.")
    return sys, context


class DebateEngine:
    """
    여러 LLMClient를 받아 토론을 진행한다.
    bull_models: 상향 논거를 맡을 모델들
    bear_models: 하향 논거를 맡을 모델들
    judge_model: 판정 모델
    """
    def __init__(self, bull_models: list[LLMClient],
                 bear_models: list[LLMClient],
                 judge_model: LLMClient):
        self.bull_models = bull_models
        self.bear_models = bear_models
        self.judge_model = judge_model

    def run(self, context: str, parse_fn) -> dict:
        """
        context = 밸류체인+시세를 요약한 텍스트.
        parse_fn = LLM 응답 문자열 -> Opinion 으로 파싱하는 함수
                   (네 프롬프트 출력 포맷에 맞춰 구현).
        실제 호출은 네 환경에서. 여기선 흐름만 정의.
        """
        opinions: list[Opinion] = []

        for m in self.bull_models:
            sys, usr = build_prompt(Role.BULL, context)
            raw = m.complete(sys, usr)
            op = parse_fn(raw, Role.BULL, m.model_name)
            if op.is_valid():
                opinions.append(op)

        for m in self.bear_models:
            sys, usr = build_prompt(Role.BEAR, context)
            raw = m.complete(sys, usr)
            op = parse_fn(raw, Role.BEAR, m.model_name)
            if op.is_valid():
                opinions.append(op)

        # 심판에게 양측 의견을 모아 넘김
        debate_text = context + "\n\n[양측 의견]\n" + "\n".join(
            f"- ({o.role.value}/{o.model}) {o.thesis}" for o in opinions
        )
        sys, usr = build_prompt(Role.JUDGE, debate_text)
        verdict_raw = self.judge_model.complete(sys, usr)

        return {"opinions": opinions, "verdict_raw": verdict_raw}
