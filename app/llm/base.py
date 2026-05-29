from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolChoiceResult:
    tool_name: str | None
    tool_input: dict[str, Any]
    reasoning: str | None = None


@dataclass(frozen=True)
class AnswerGenerationResult:
    answer: str
    confidence: str
    source: str
    rationale: str | None = None


@dataclass(frozen=True)
class EvalCriterionResult:
    criterion: str
    passed: bool
    explanation: str


@dataclass(frozen=True)
class EvalGradingResult:
    passed: bool
    summary: str
    criteria: list[EvalCriterionResult]


class LLMClient(Protocol):
    provider: str
    model: str

    def choose_tool(
        self,
        *,
        user_input: str,
        available_tools: list[str],
        system_prompt: str | None = None,
    ) -> ToolChoiceResult:
        ...

    def generate_answer(
        self,
        *,
        user_input: str,
        tool_name: str | None,
        tool_result: Any,
        system_prompt: str | None = None,
    ) -> AnswerGenerationResult:
        ...

    def run_diagnostic_probe(self) -> str:
        ...

    def grade_eval_case(
        self,
        *,
        case_id: str,
        case_title: str,
        evaluation_target: str,
        conversation_transcript: str,
        final_answer: str,
        selected_tool: str | None,
        pass_criteria: list[str],
    ) -> EvalGradingResult:
        ...
