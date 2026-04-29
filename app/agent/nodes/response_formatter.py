import re
import logging
from typing import Any

from app.agent.state import AgentState
from app.llm import build_llm_from_env
from app.llm.factory import load_system_prompt
from app.models import AgentResponse

logger = logging.getLogger(__name__)


def _format_customer(result: dict[str, Any]) -> AgentResponse:
    return AgentResponse(
        answer=(
            f"{result['fullName']} ({result['customerId']}) is a {result['segment']} customer "
            f"with status {result['status']} and risk rating {result['riskRating']}."
        ),
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _format_customer_profile_and_alerts(result: dict[str, Any]) -> AgentResponse:
    profile = result.get("customer_profile", {})
    alerts = result.get("alerts", [])
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(alerts, list):
        alerts = []

    customer_id = profile.get("customerId", "the customer")
    risk = profile.get("riskRating", "unknown")
    status = profile.get("status", "unknown")

    if alerts:
        alert_summary = "; ".join(
            f"{item.get('alertId')} {item.get('severity')} {item.get('type')}" for item in alerts[:3]
        )
        answer = (
            f"{customer_id} has risk rating {risk} and status {status}. "
            f"There are {len(alerts)} active alerts: {alert_summary}."
        )
    else:
        answer = f"{customer_id} has risk rating {risk} and status {status}, with no active alerts found."

    return AgentResponse(
        answer=answer,
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _format_transactions(result: list[dict[str, Any]]) -> AgentResponse:
    if not result:
        return AgentResponse(
            answer="No matching transactions were found.",
            confidence="high",
            source="tool",
            data_points=[],
        )
    summary = [
        f"{item['transactionId']} {item['merchant']} {item['amount']} {item['currency']}"
        for item in result[:5]
    ]
    return AgentResponse(
        answer="Found matching transactions: " + "; ".join(summary),
        confidence="high",
        source="tool",
        data_points=result,
    )


def _format_spending_summary(result: dict[str, Any]) -> AgentResponse:
    return AgentResponse(
        answer=(
            f"Total spend for {result['customerId']} is {result['totalSpend']} grouped by "
            f"{result['groupBy']}."
        ),
        confidence="high",
        source="tool",
        data_points=result.get("breakdown", []),
    )


def _format_alerts(result: list[dict[str, Any]]) -> AgentResponse:
    if not result:
        return AgentResponse(
            answer="No matching alerts were found.",
            confidence="high",
            source="tool",
            data_points=[],
        )
    summary = [f"{item['alertId']} {item['severity']} {item['type']}" for item in result[:5]]
    return AgentResponse(
        answer="Found matching alerts: " + "; ".join(summary),
        confidence="high",
        source="tool",
        data_points=result,
    )


def _format_runtime_diagnostic(result: dict[str, Any]) -> AgentResponse:
    provider = result.get("provider")
    model = result.get("model")
    mode = result.get("mode")
    summary = result.get("summary")
    live_probe = result.get("live_probe")

    if isinstance(live_probe, str) and live_probe.strip():
        answer = live_probe.strip()
    else:
        answer = "No LLM - Hardcoded path."

    return AgentResponse(
        answer=answer,
        confidence="high",
        source="tool",
        data_points=[{"mode": mode, "provider": provider, "model": model, "summary": summary}],
    )


def format_response(state: AgentState) -> AgentResponse:
    if isinstance(state.raw_result, dict) and "error" in state.raw_result:
        return AgentResponse(
            answer=state.raw_result["error"],
            confidence="low",
            source="model",
            data_points=[state.raw_result],
            selected_tool=state.selected_tool,
            tool_input=state.tool_input,
            tool_reasoning=state.tool_reasoning,
            llm_routing_error=state.llm_routing_error,
            llm_answer_error=state.llm_answer_error,
        )

    runtime = build_llm_from_env()
    if runtime.is_ready and runtime.client and state.selected_tool and state.raw_result is not None:
        try:
            generated = runtime.client.generate_answer(
                user_input=state.user_input,
                tool_name=state.selected_tool,
                tool_result=state.raw_result,
                system_prompt=load_system_prompt(),
            )
            if generated.answer:
                return AgentResponse(
                    answer=generated.answer,
                    confidence=generated.confidence,
                    source=generated.source,
                    data_points=state.raw_result if isinstance(state.raw_result, list) else [state.raw_result],
                    selected_tool=state.selected_tool,
                    tool_input=state.tool_input,
                    tool_reasoning=state.tool_reasoning,
                    answer_rationale=generated.rationale,
                    llm_routing_error=state.llm_routing_error,
                    llm_answer_error=state.llm_answer_error,
                )
        except Exception as exc:
            logger.exception(
                "LLM answer generation failed for tool %s and input: %s",
                state.selected_tool,
                state.user_input,
            )
            state.llm_answer_error = f"{type(exc).__name__}: {exc}"
            return AgentResponse(
                answer=f"LLM answer generation failed: {type(exc).__name__}: {exc}",
                confidence="low",
                source="model",
                data_points=state.raw_result if isinstance(state.raw_result, list) else [state.raw_result],
                selected_tool=state.selected_tool,
                tool_input=state.tool_input,
                tool_reasoning=state.tool_reasoning,
                llm_routing_error=state.llm_routing_error,
                llm_answer_error=state.llm_answer_error,
            )

    if state.selected_tool == "identify_runtime" and isinstance(state.raw_result, dict):
        response = _format_runtime_diagnostic(state.raw_result)
    elif state.selected_tool == "get_customer_profile" and isinstance(state.raw_result, dict):
        response = _format_customer(state.raw_result)
    elif state.selected_tool == "get_customer_profile_and_alerts" and isinstance(state.raw_result, dict):
        response = _format_customer_profile_and_alerts(state.raw_result)
    elif state.selected_tool == "get_transactions" and isinstance(state.raw_result, list):
        response = _format_transactions(state.raw_result)
    elif state.selected_tool == "get_spending_summary" and isinstance(state.raw_result, dict):
        response = _format_spending_summary(state.raw_result)
    elif state.selected_tool == "get_alerts" and isinstance(state.raw_result, list):
        response = _format_alerts(state.raw_result)
    else:
        customer_ids = re.findall(r"\bCUS\d{3}\b", state.user_input.upper())
        if len(customer_ids) > 1:
            response = AgentResponse(
                answer=(
                    "This scaffold does not support multi-customer comparisons yet. "
                    "Try asking about one customer at a time, or implement a dedicated chained workflow for comparisons."
                ),
                confidence="low",
                source="model",
                data_points=[],
            )
        else:
            response = AgentResponse(
                answer=(
                    "I could not map that request to a banking tool yet. Try asking about a "
                    "customer, fraud transactions, spending summary, or alerts."
                ),
                confidence="low",
                source="model",
                data_points=[],
            )

    response.selected_tool = state.selected_tool
    response.tool_input = state.tool_input
    response.tool_reasoning = state.tool_reasoning
    response.llm_routing_error = state.llm_routing_error
    response.llm_answer_error = state.llm_answer_error
    return response
