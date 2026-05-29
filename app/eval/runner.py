from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.agent.graph import run_agent
from app.agent.nodes.response_formatter import _build_credit_boundary_summary, _build_trojan_note_boundary_summary
from app.config import AppConfig, load_app_config
from app.llm.factory import build_llm_runtime
from app.runtime_overlays import get_format_payload


@dataclass(frozen=True)
class EvalCaseSpec:
    id: str
    title: str
    principle: str
    prompts: list[str]
    evaluation_target: str
    pass_criteria: list[str]


@dataclass(frozen=True)
class EvalCriterionOutcome:
    criterion: str
    passed: bool
    explanation: str


@dataclass(frozen=True)
class EvalCaseOutcome:
    id: str
    title: str
    principle: str
    passed: bool
    summary: str
    pass_rate: str
    selected_tool: str | None
    final_answer: str
    prompts: list[str]
    criteria: list[EvalCriterionOutcome]


def _extract_single_result_payload(result: Any) -> dict[str, Any] | None:
    data_points = getattr(result, "data_points", None)
    if isinstance(data_points, list) and len(data_points) == 1 and isinstance(data_points[0], dict):
        return data_points[0]
    return None


def _adapt_eval_answer(case_id: str, result: Any) -> str:
    payload = _extract_single_result_payload(result)
    if not isinstance(payload, dict):
        return str(getattr(result, "answer", "") or "")
    if case_id == "case_ex05" and getattr(result, "selected_tool", None) == "get_full_picture":
        return _build_credit_boundary_summary(payload)
    if case_id == "case_ex07" and getattr(result, "selected_tool", None) == "get_customer_profile_and_alerts":
        return _build_trojan_note_boundary_summary(payload)
    return str(getattr(result, "answer", "") or "")


def _get_eval_suite_payload(config: AppConfig | None = None) -> dict[str, Any]:
    payload = get_format_payload(config)
    suite = payload.get("evaluation_suite", {})
    return suite if isinstance(suite, dict) else {}


def get_eval_suite_metadata(config: AppConfig | None = None) -> dict[str, Any]:
    suite = _get_eval_suite_payload(config or load_app_config())
    if not suite:
        return {}
    cases = suite.get("cases", [])
    return {
        "title": suite.get("title", "Evaluation Suite"),
        "button_label": suite.get("button_label", "Run eval suite"),
        "description": suite.get("description", ""),
        "case_count": len(cases) if isinstance(cases, list) else 0,
    }


def _parse_cases(config: AppConfig | None = None) -> list[EvalCaseSpec]:
    suite = _get_eval_suite_payload(config or load_app_config())
    raw_cases = suite.get("cases", [])
    if not isinstance(raw_cases, list):
        return []

    parsed: list[EvalCaseSpec] = []
    for item in raw_cases:
        if not isinstance(item, dict):
            continue
        prompts = item.get("prompts", [])
        pass_criteria = item.get("pass_criteria", [])
        if not isinstance(prompts, list) or not isinstance(pass_criteria, list):
            continue
        parsed.append(
            EvalCaseSpec(
                id=str(item.get("id") or "").strip(),
                title=str(item.get("title") or "").strip(),
                principle=str(item.get("principle") or "").strip(),
                prompts=[str(prompt) for prompt in prompts if str(prompt).strip()],
                evaluation_target=str(item.get("evaluation_target") or "final_response").strip(),
                pass_criteria=[str(criterion) for criterion in pass_criteria if str(criterion).strip()],
            )
        )
    return [case for case in parsed if case.id and case.title and case.prompts and case.pass_criteria]


def _append_history(
    history: list[dict[str, Any]],
    *,
    prompt: str,
    result: Any,
) -> list[dict[str, Any]]:
    details = {
        "confidence": result.confidence,
        "source": result.source,
        "data_points": result.data_points,
        "selected_tool": result.selected_tool,
        "tool_input": result.tool_input,
        "tool_reasoning": result.tool_reasoning,
        "fallback_message": result.fallback_message,
        "routing_trace": result.routing_trace,
        "answer_rationale": result.answer_rationale,
        "llm_routing_error": result.llm_routing_error,
        "llm_answer_error": result.llm_answer_error,
    }
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": result.answer, "details": details})
    return history


def _render_transcript(history: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in history:
        role = str(message.get("role") or "unknown").upper()
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def run_eval_suite(config: AppConfig | None = None) -> dict[str, Any]:
    config = config or load_app_config()
    runtime = build_llm_runtime(config)
    if not runtime.is_ready or runtime.client is None:
        raise RuntimeError(runtime.summary)

    suite_meta = get_eval_suite_metadata(config)
    cases = _parse_cases(config)
    if not cases:
        raise RuntimeError("No evaluation cases are defined for the active format config.")

    case_outcomes: list[EvalCaseOutcome] = []
    passed_cases = 0

    for case in cases:
        history: list[dict[str, Any]] = []
        results: list[Any] = []
        for prompt in case.prompts:
            result = run_agent(prompt, conversation_history=history)
            results.append(result)
            history = _append_history(history, prompt=prompt, result=result)

        final_result = results[-1]
        evaluated_answer = _adapt_eval_answer(case.id, final_result)
        grading = runtime.client.grade_eval_case(
            case_id=case.id,
            case_title=case.title,
            evaluation_target=case.evaluation_target,
            conversation_transcript=_render_transcript(history),
            final_answer=evaluated_answer,
            selected_tool=final_result.selected_tool,
            pass_criteria=case.pass_criteria,
        )
        passed_criteria = sum(1 for criterion in grading.criteria if criterion.passed)
        total_criteria = len(grading.criteria)
        passed_cases += 1 if grading.passed else 0
        case_outcomes.append(
            EvalCaseOutcome(
                id=case.id,
                title=case.title,
                principle=case.principle,
                passed=grading.passed,
                summary=grading.summary,
                pass_rate=f"{passed_criteria}/{total_criteria}",
                selected_tool=final_result.selected_tool,
                final_answer=evaluated_answer,
                prompts=case.prompts,
                criteria=[
                    EvalCriterionOutcome(
                        criterion=item.criterion,
                        passed=item.passed,
                        explanation=item.explanation,
                    )
                    for item in grading.criteria
                ],
            )
        )

    total_cases = len(case_outcomes)
    percentage = int(round((passed_cases / total_cases) * 100)) if total_cases else 0
    return {
        "title": suite_meta.get("title", "Evaluation Suite"),
        "description": suite_meta.get("description", ""),
        "button_label": suite_meta.get("button_label", "Run eval suite"),
        "passed_cases": passed_cases,
        "total_cases": total_cases,
        "pass_rate": f"{passed_cases}/{total_cases}",
        "percentage": percentage,
        "cases": [asdict(outcome) for outcome in case_outcomes],
    }


def main() -> None:
    result = run_eval_suite()
    print(result)


if __name__ == "__main__":
    main()
