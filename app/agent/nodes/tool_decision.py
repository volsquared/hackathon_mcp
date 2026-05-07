import logging
import re

from app.agent.state import AgentState
from app.llm import build_llm_from_env
from app.llm.factory import load_available_tools, load_system_prompt, load_tool_descriptions

logger = logging.getLogger(__name__)

GENTLE_FALLBACK = "I'm not sure what you're looking for. Could you rephrase?"


def _extract_customer_id(text: str) -> str | None:
    match = re.search(r"\bCUS\d{3}\b", text.upper())
    return match.group(0) if match else None


def _is_runtime_diagnostic_request(text: str) -> bool:
    normalized = text.lower()
    markers = (
        "identify the llm agent",
        "identify llm agent",
        "which llm agent",
        "what llm agent",
        "what agent is this",
        "which agent is this",
    )
    return any(marker in normalized for marker in markers)


def _record_deterministic_trace(state: AgentState, *, matched_keyword: str | None, fallback_triggered: bool) -> AgentState:
    state.routing_trace = {
        "routing_mode": "deterministic",
        "matched_keyword": matched_keyword or "none",
        "selected_tool": state.selected_tool or "none",
        "fallback_triggered": fallback_triggered,
    }
    return state


def _record_llm_trace(state: AgentState, *, decision_source: str) -> AgentState:
    state.routing_trace = {
        "routing_mode": "llm",
        "matched_keyword": "none",
        "selected_tool": state.selected_tool or "none",
        "fallback_triggered": False,
        "decision_source": decision_source,
    }
    return state


def _log_route_decision(state: AgentState, reason: str) -> None:
    logger.info(
        "tool-selection input=%r mode=%s matched_keyword=%s selected_tool=%s fallback=%s reason=%s",
        state.user_input,
        state.routing_trace.get("routing_mode", "unknown"),
        state.routing_trace.get("matched_keyword", "none"),
        state.routing_trace.get("selected_tool", "none"),
        state.routing_trace.get("fallback_triggered", False),
        reason,
    )


def _deterministic_decide_tool(state: AgentState) -> AgentState:
    text = state.user_input.lower()
    customer_id = _extract_customer_id(state.user_input)
    state.fallback_message = None

    if customer_id and ("profile" in text or "risk" in text):
        state.selected_tool = "get_customer_profile"
        state.tool_input = {"customer_id": customer_id}
        matched_keyword = "profile" if "profile" in text else "risk"
        state.tool_reasoning = f"Matched the hardcoded {matched_keyword} keyword."
        state = _record_deterministic_trace(state, matched_keyword=matched_keyword, fallback_triggered=False)
        _log_route_decision(state, "matched deterministic keyword")
        return state

    if customer_id and "alert" in text:
        state.selected_tool = "get_alerts"
        state.tool_input = {"customer_id": customer_id}
        state.tool_reasoning = "Matched the hardcoded alert keyword."
        state = _record_deterministic_trace(state, matched_keyword="alert", fallback_triggered=False)
        _log_route_decision(state, "matched deterministic keyword")
        return state

    if customer_id and ("spend" in text or "summary" in text):
        state.selected_tool = "get_spending_summary"
        state.tool_input = {"customer_id": customer_id, "group_by": "category"}
        state.tool_reasoning = "Matched the hardcoded spend/summary keyword."
        state = _record_deterministic_trace(state, matched_keyword="spend/summary", fallback_triggered=False)
        _log_route_decision(state, "matched deterministic keyword")
        return state

    if customer_id and ("fraud" in text or "transaction" in text):
        state.selected_tool = "get_transactions"
        state.tool_input = {"customer_id": customer_id, "fraud_only": "fraud" in text}
        state.tool_reasoning = "Matched the hardcoded fraud/transaction keyword."
        state = _record_deterministic_trace(state, matched_keyword="fraud/transaction", fallback_triggered=False)
        _log_route_decision(state, "matched deterministic keyword")
        return state

    state.selected_tool = None
    state.tool_input = {}
    state.tool_reasoning = "No hardcoded keyword matched. Returning the gentle catch-all."
    state.fallback_message = GENTLE_FALLBACK
    state = _record_deterministic_trace(state, matched_keyword=None, fallback_triggered=True)
    _log_route_decision(state, "no deterministic keyword matched")
    return state


def decide_tool(state: AgentState) -> AgentState:
    if _is_runtime_diagnostic_request(state.user_input):
        state.selected_tool = "identify_runtime"
        state.tool_input = {}
        state.tool_reasoning = "Matched the built-in runtime diagnostic request."
        state.fallback_message = None
        state = _record_deterministic_trace(state, matched_keyword="runtime_diagnostic", fallback_triggered=False)
        _log_route_decision(state, "matched runtime diagnostic request")
        return state

    runtime = build_llm_from_env()
    available_tools = load_available_tools()

    if runtime.is_ready and runtime.client and available_tools:
        try:
            result = runtime.client.choose_tool(
                user_input=state.user_input,
                available_tools=available_tools,
                tool_descriptions=load_tool_descriptions(),
                system_prompt=load_system_prompt(),
            )
            if result.tool_name:
                state.selected_tool = result.tool_name
                state.tool_input = result.tool_input
                state.tool_reasoning = result.reasoning or "Selected by the LLM based on semantic intent."
                state.fallback_message = None
                state = _record_llm_trace(state, decision_source="semantic intent")
                _log_route_decision(state, "selected by llm")
                return state
        except Exception as exc:
            logger.exception("LLM tool routing failed for input: %s", state.user_input)
            state.llm_routing_error = f"{type(exc).__name__}: {exc}"

    return _deterministic_decide_tool(state)
